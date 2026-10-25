"""Bounded binary extraction, performed inside the execution sandbox.

Never read a model-provided path from the Auxilia host filesystem. Walk with
openat/O_NOFOLLOW so symlink swaps cannot escape the allowed output roots.
"""

import base64
import io
import json
import shlex
import zipfile
from pathlib import PurePosixPath

from deepagents.backends.sandbox import BaseSandbox

from app.exceptions import DomainValidationError


PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

TEXT_MIME_BY_SUFFIX = {
    ".bash": "application/x-sh",
    ".c": "text/x-c",
    ".cc": "text/x-c++",
    ".conf": "text/plain",
    ".cpp": "text/x-c++",
    ".css": "text/css",
    ".csv": "text/csv",
    ".cts": "text/typescript",
    ".env": "text/plain",
    ".go": "text/x-go",
    ".graphql": "application/graphql",
    ".gql": "application/graphql",
    ".h": "text/x-c",
    ".hpp": "text/x-c++",
    ".htm": "text/html",
    ".html": "text/html",
    ".ini": "text/plain",
    ".java": "text/x-java-source",
    ".js": "text/javascript",
    ".json": "application/json",
    ".jsonc": "application/json",
    ".jsonl": "application/x-ndjson",
    ".jsonld": "application/ld+json",
    ".jsx": "text/jsx",
    ".kt": "text/x-kotlin",
    ".kts": "text/x-kotlin",
    ".less": "text/css",
    ".lua": "text/x-lua",
    ".markdown": "text/markdown",
    ".md": "text/markdown",
    ".mjs": "text/javascript",
    ".mts": "text/typescript",
    ".ndjson": "application/x-ndjson",
    ".ipynb": "application/json",
    ".php": "application/x-httpd-php",
    ".properties": "text/plain",
    ".py": "text/x-python",
    ".pyi": "text/x-python",
    ".r": "text/x-r",
    ".rb": "text/x-ruby",
    ".rs": "text/x-rust",
    ".sass": "text/css",
    ".scss": "text/css",
    ".sh": "application/x-sh",
    ".sql": "application/sql",
    ".svelte": "text/plain",
    ".swift": "text/x-swift",
    ".toml": "application/toml",
    ".ts": "text/typescript",
    ".tsx": "text/tsx",
    ".txt": "text/plain",
    ".vue": "text/plain",
    ".xml": "application/xml",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".zsh": "application/x-sh",
}

TEXT_MIME_BY_FILENAME = {
    ".env": "text/plain",
    "dockerfile": "text/plain",
    "makefile": "text/plain",
}


class SandboxFileMissingError(Exception):
    pass


class SandboxReadError(Exception):
    """The sandbox could not be reached or failed to run the read."""


READ_SCRIPT = r"""
import os, stat, sys, base64, json
path, roots, limit = json.loads(sys.argv[1])
if not path.startswith('/') or '..' in path.split('/'):
    raise ValueError('Absolute output path required; traversal is forbidden')
path = os.path.normpath(path)
if not any(path.startswith(root.rstrip('/') + '/') for root in roots):
    raise ValueError('File must be in an allowed output directory')
fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
try:
    parts = path.strip('/').split('/')
    for part in parts[:-1]:
        child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        os.close(fd)
        fd = child
    file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    with os.fdopen(file_fd, 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('Not a regular file or file exceeds artifact size limit')
        data = source.read(limit + 1)
        if len(data) > limit:
            raise ValueError('File exceeds artifact size limit')
    print(base64.b64encode(data).decode('ascii'))
except FileNotFoundError:
    sys.exit(44)
finally:
    os.close(fd)
"""


def read_bytes(backend: BaseSandbox, path: str, roots: list[str], limit: int) -> bytes:
    args = json.dumps([path, roots, limit])
    command = f"python3 -c {shlex.quote(READ_SCRIPT)} {shlex.quote(args)}"
    try:
        # Runs inside the sandbox shell, not SQL; args are shlex-quoted JSON.
        result = backend.execute(command, timeout=60)  # nosemgrep
    except Exception as exc:  # provider SDKs raise their own transport errors
        raise SandboxReadError(path) from exc
    if result.exit_code == 44:
        raise SandboxFileMissingError(path)
    if result.exit_code != 0 or result.truncated:
        raise DomainValidationError(
            "Cannot read artifact: use a regular file in an allowed output directory within the size limit (symlinks are not supported)."
        )
    try:
        data = base64.b64decode(result.output.strip(), validate=True)
    except ValueError as exc:
        raise DomainValidationError("Sandbox returned an invalid artifact") from exc
    if len(data) > limit:
        raise DomainValidationError("Artifact exceeds the size limit")
    return data


def text_encoding(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    sample = data[:256]
    pairs = len(sample) // 2
    if pairs >= 2:
        even_zeroes = sample[: pairs * 2 : 2].count(0)
        odd_zeroes = sample[1 : pairs * 2 : 2].count(0)
        if odd_zeroes > pairs / 2 and even_zeroes < pairs / 10:
            return "utf-16-le"
        if even_zeroes > pairs / 2 and odd_zeroes < pairs / 10:
            return "utf-16-be"
    return "utf-8-sig"


def detect_mime(filename: str, data: bytes) -> str:
    name = PurePosixPath(filename).name.lower()
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix == ".pptx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if (
                    len(entries) > 10000
                    or sum(x.file_size for x in entries) > 100 * 1024 * 1024
                ):
                    raise DomainValidationError(
                        "Presentation expands beyond the preview limit"
                    )
                if "ppt/presentation.xml" not in archive.namelist():
                    raise DomainValidationError("Invalid PowerPoint presentation")
        except zipfile.BadZipFile as exc:
            raise DomainValidationError("Invalid PowerPoint presentation") from exc
        return PPTX_MIME
    if suffix == ".pdf" and data.startswith(b"%PDF-"):
        return "application/pdf"
    text_mime = TEXT_MIME_BY_FILENAME.get(name) or TEXT_MIME_BY_SUFFIX.get(suffix)
    if text_mime is not None:
        try:
            text = data.decode(text_encoding(data))
        except UnicodeDecodeError:
            try:
                text = data.decode("cp1252")
            except UnicodeDecodeError:
                return "application/octet-stream"
        if not any(ord(char) < 32 and char not in "\t\n\r\f\x1b" for char in text):
            return text_mime
        return "application/octet-stream"

    # An uncommon or extensionless UTF-8 text file remains previewable as
    # plain text. Reject C0 controls so arbitrary binary payloads keep the
    # download-only application/octet-stream treatment.
    try:
        text = data.decode(text_encoding(data))
    except UnicodeDecodeError:
        return "application/octet-stream"
    if not any(ord(char) < 32 and char not in "\t\n\r\f\x1b" for char in text):
        return "text/plain"
    return "application/octet-stream"
