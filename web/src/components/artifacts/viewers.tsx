"use client";

import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType } from "react";
import Papa from "papaparse";
import { Streamdown } from "streamdown";
import { Loader2, Maximize } from "lucide-react";
import { cn } from "@/lib/utils";
import { getHtmlSources } from "@/lib/api/resources/artifacts";
import {
  CodeBlock,
  SHIKI_MAX_CHARS,
} from "@/components/ai-elements/code-block";
import type { BundledLanguage, SpecialLanguage } from "shiki";
import type { Artifact } from "@/lib/api/resources/artifacts";

export interface ViewerProps {
  artifact: Artifact;
  bytes: ArrayBuffer;
  /** Set when the viewer may save edits over the artifact. */
  onSave?: (bytes: Uint8Array) => Promise<void>;
}
export interface ViewerAdapter {
  id: string;
  supports: (mime: string) => boolean;
  component: ComponentType<ViewerProps>;
}
export function Loading({
  label,
  className,
}: {
  label: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={cn(
        "flex h-full min-h-40 flex-col items-center justify-center gap-2.5 text-sm text-meta",
        className,
      )}
    >
      <Loader2 className="size-5 animate-spin text-petrol" />
      <span>{label}</span>
    </div>
  );
}
const PptxViewer = lazy(() => import("./pptx-viewer"));
const decoder = (bytes: ArrayBuffer, fatal = false) => {
  const prefix = new Uint8Array(bytes, 0, Math.min(bytes.byteLength, 2));
  const sample = new Uint8Array(bytes, 0, Math.min(bytes.byteLength, 256));
  const pairs = Math.floor(sample.length / 2);
  let evenZeroes = 0;
  let oddZeroes = 0;
  for (let index = 0; index < pairs * 2; index += 2) {
    if (sample[index] === 0) evenZeroes += 1;
    if (sample[index + 1] === 0) oddZeroes += 1;
  }
  const encoding =
    prefix[0] === 0xff && prefix[1] === 0xfe
      ? "utf-16le"
      : prefix[0] === 0xfe && prefix[1] === 0xff
        ? "utf-16be"
        : pairs >= 2 && oddZeroes > pairs / 2 && evenZeroes < pairs / 10
          ? "utf-16le"
          : pairs >= 2 && evenZeroes > pairs / 2 && oddZeroes < pairs / 10
            ? "utf-16be"
        : "utf-8";
  return new TextDecoder(encoding, { fatal });
};
const decode = (bytes: ArrayBuffer) => decoder(bytes).decode(bytes);

export function isolatedHtml(html: string, sources: string[]): string {
  // Placed before all authored content. The frame has an opaque origin: no
  // cookies, auxilia API, forms, nested frames, fetch or host bridge. Scripts
  // run, and may load libraries, styles, fonts and images from the workspace's
  // allowed sources (ARTIFACT_HTML_SOURCES, validated by the backend).
  const remote = sources.map((source) => ` ${source}`).join("");
  return `<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'${remote}; style-src 'unsafe-inline'${remote}; img-src data: blob:${remote}; font-src data:${remote}; media-src data: blob:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'">${html}`;
}
const pill =
  "flex h-8 cursor-pointer items-center justify-center gap-1.5 rounded-full border border-border bg-white/90 text-[12px] font-semibold text-subtle shadow-[0_2px_8px_rgba(10,25,30,0.08)] backdrop-blur hover:bg-hover hover:text-ink";

function WebPageViewer({ bytes }: ViewerProps) {
  const box = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const [sources, setSources] = useState<string[]>();
  const limit = 1024 * 1024;
  const preview = bytes.byteLength > limit ? bytes.slice(0, limit) : bytes;
  useEffect(() => {
    void getHtmlSources().then(setSources);
  }, []);
  if (!sources) return <Loading label="Loading page…" />;
  return (
    <div className="flex h-full min-h-96 flex-col">
      {preview !== bytes && <PreviewLimitNote />}
      {/* The toolbar hides in full screen; Esc exits. */}
      <div
        ref={box}
        className="relative min-h-0 flex-1 bg-white [&:fullscreen>div]:hidden"
      >
        <iframe
          ref={frame}
          title="HTML artifact"
          className="h-full w-full border-0 bg-white"
          sandbox="allow-scripts"
          referrerPolicy="no-referrer"
          srcDoc={isolatedHtml(decode(preview), sources)}
        />
        <div className="absolute right-3 top-3 flex gap-2">
          <button
            type="button"
            aria-label="Full screen"
            title="Full screen"
            onClick={() => {
              // Focus the page so its own keys (e.g. arrows in a deck) work.
              // Rejected when the browser or an embedding policy denies it: stay inline.
              box.current
                ?.requestFullscreen()
                .then(() => frame.current?.focus())
                .catch(() => undefined);
            }}
            className={cn(pill, "w-8")}
          >
            <Maximize className="size-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
function PdfViewer({ bytes }: ViewerProps) {
  const [url, setUrl] = useState<string>();
  useEffect(() => {
    const next = URL.createObjectURL(
      new Blob([bytes], { type: "application/pdf" }),
    );
    // URL lifetime is owned by this effect and cleaned up on replacement.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUrl(next);
    return () => {
      URL.revokeObjectURL(next);
    };
  }, [bytes]);
  return url ? (
    <iframe title="PDF artifact" src={url} className="h-full min-h-96 w-full" />
  ) : null;
}
function MarkdownViewer({ bytes }: ViewerProps) {
  const limit = 512 * 1024;
  const preview = bytes.byteLength > limit ? bytes.slice(0, limit) : bytes;
  return (
    <>
      {preview !== bytes && <PreviewLimitNote />}
      <div className="prose dark:prose-invert p-4">
        <Streamdown
          mode="static"
          allowedTags={{}}
          components={{ img: () => <span>[Image omitted]</span> }}
        >
          {decode(preview)}
        </Streamdown>
      </div>
    </>
  );
}
function TextViewer({ bytes }: ViewerProps) {
  const limit = 512 * 1024;
  const preview = bytes.byteLength > limit ? bytes.slice(0, limit) : bytes;
  return (
    <>
      {preview !== bytes && <PreviewLimitNote />}
      <pre className="whitespace-pre-wrap break-words p-4 text-sm">
        {decode(preview)}
      </pre>
    </>
  );
}
const LANGUAGES_BY_MIME = new Map<string, BundledLanguage>(
  Object.entries({
    "application/json": "json",
    "application/ld+json": "json",
    "application/toml": "toml",
    "application/xml": "xml",
    "application/x-httpd-php": "php",
    "application/x-javascript": "javascript",
    "application/x-ndjson": "json",
    "application/x-sh": "bash",
    "application/x-toml": "toml",
    "application/x-yaml": "yaml",
    "application/yaml": "yaml",
    "text/css": "css",
    "text/javascript": "javascript",
    "text/jsx": "jsx",
    "text/toml": "toml",
    "text/tsx": "tsx",
    "text/typescript": "typescript",
    "text/x-python": "python",
    "text/xml": "xml",
    "text/yaml": "yaml",
  } satisfies Record<string, BundledLanguage>),
);

const LANGUAGES_BY_EXTENSION = new Map<string, BundledLanguage>(
  Object.entries({
    astro: "astro",
    bash: "bash",
    c: "c",
    cc: "cpp",
    conf: "ini",
    cpp: "cpp",
    cs: "csharp",
    css: "css",
    cts: "typescript",
    dart: "dart",
    env: "dotenv",
    ex: "elixir",
    exs: "elixir",
    fish: "fish",
    go: "go",
    gql: "graphql",
    graphql: "graphql",
    h: "c",
    hpp: "cpp",
    htm: "html",
    html: "html",
    ini: "ini",
    java: "java",
    js: "javascript",
    json: "json",
    jsonc: "jsonc",
    jsonl: "json",
    jsonld: "json",
    jsx: "jsx",
    kt: "kotlin",
    kts: "kotlin",
    less: "less",
    lua: "lua",
    markdown: "markdown",
    md: "markdown",
    mjs: "javascript",
    mts: "typescript",
    ndjson: "json",
    ipynb: "json",
    php: "php",
    proto: "proto",
    properties: "properties",
    ps1: "powershell",
    py: "python",
    pyi: "python",
    r: "r",
    rb: "ruby",
    rs: "rust",
    sass: "sass",
    scss: "scss",
    scala: "scala",
    sh: "bash",
    sql: "sql",
    svelte: "svelte",
    swift: "swift",
    tf: "hcl",
    toml: "toml",
    ts: "typescript",
    tsx: "tsx",
    vue: "vue",
    xml: "xml",
    zig: "zig",
    svg: "xml",
    yaml: "yaml",
    yml: "yaml",
    zsh: "bash",
  } satisfies Record<string, BundledLanguage>),
);

const LANGUAGES_BY_FILENAME = new Map<string, BundledLanguage>([
  [".bashrc", "bash"],
  [".env", "dotenv"],
  [".zshrc", "bash"],
  ["dockerfile", "dockerfile"],
  ["makefile", "makefile"],
]);

function basename(filename: string): string {
  return filename.split(/[\\/]/).at(-1)?.toLowerCase() ?? "";
}

function extension(filename: string): string {
  const name = basename(filename);
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot + 1) : "";
}

function codeLanguage(
  artifact: Artifact,
): BundledLanguage | SpecialLanguage {
  const mime = artifact.mime_type.toLowerCase().split(";", 1)[0];
  const name = basename(artifact.filename);
  return (
    LANGUAGES_BY_FILENAME.get(name) ??
    (name.startsWith("dockerfile.") ? "dockerfile" : undefined) ??
    LANGUAGES_BY_EXTENSION.get(extension(artifact.filename)) ??
    LANGUAGES_BY_MIME.get(mime) ??
    "plaintext"
  );
}

const TEXT_APPLICATION_MIMES = new Set([
  "application/graphql",
  "application/javascript",
  "application/sql",
  "application/x-ndjson",
]);
const BINARY_CONTROL = /[\u0000-\u0008\u000b\u000e-\u001a\u001c-\u001f]/;

function scansAsText(bytes: ArrayBuffer, textDecoder: TextDecoder): boolean {
  const chunkSize = 64 * 1024;
  for (let offset = 0; offset < bytes.byteLength; offset += chunkSize) {
    const length = Math.min(chunkSize, bytes.byteLength - offset);
    const chunk = new Uint8Array(bytes, offset, length);
    const text = textDecoder.decode(chunk, {
      stream: offset + length < bytes.byteLength,
    });
    if (BINARY_CONTROL.test(text)) return false;
  }
  return true;
}

function containsText(artifact: Artifact, bytes: ArrayBuffer): boolean {
  try {
    return scansAsText(bytes, decoder(bytes, true));
  } catch {
    const mime = artifact.mime_type.toLowerCase().split(";", 1)[0];
    const claimedText =
      mime.startsWith("text/") ||
      LANGUAGES_BY_MIME.has(mime) ||
      TEXT_APPLICATION_MIMES.has(mime) ||
      codeLanguage(artifact) !== "plaintext";
    if (!claimedText) return false;
    return scansAsText(bytes, new TextDecoder("windows-1252"));
  }
}

function isTextArtifact(artifact: Artifact, bytes: ArrayBuffer): boolean {
  return containsText(artifact, bytes);
}

function CodeViewer({ artifact, bytes }: ViewerProps) {
  const byteLimit = SHIKI_MAX_CHARS * 4;
  const source = bytes.byteLength > byteLimit ? bytes.slice(0, byteLimit) : bytes;
  const decoded = decode(source);
  const code = decoded.slice(0, SHIKI_MAX_CHARS);
  const truncated = source !== bytes || decoded.length > SHIKI_MAX_CHARS;
  return (
    <>
      {truncated && <PreviewLimitNote />}
      <CodeBlock
        code={code}
        language={codeLanguage(artifact)}
        showLineNumbers
        className="rounded-none"
      />
    </>
  );
}

const PreviewLimitNote = () => (
  <p className="border-b border-border px-4 py-2 text-xs text-muted-foreground">
    Preview truncated for performance. Download for the complete file.
  </p>
);
function CsvViewer({ bytes }: ViewerProps) {
  const limit = 1024 * 1024;
  const preview = useMemo(
    () => (bytes.byteLength > limit ? bytes.slice(0, limit) : bytes),
    [bytes, limit],
  );
  const result = useMemo(
    () =>
      Papa.parse<string[]>(decode(preview), {
        preview: 501,
        skipEmptyLines: true,
      }),
    [preview],
  );
  const rows = result.data.slice(0, 500);
  return (
    <div className="overflow-auto p-3">
      <p className="mb-3 text-xs text-muted-foreground">
        Preview: up to 500 rows, 50 columns, and 1 MB. Download for the complete
        file.
      </p>
      <table className="w-full border-collapse text-sm">
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.slice(0, 50).map((cell, j) => (
                <td
                  key={j}
                  className="max-w-80 truncate border p-2"
                  title={cell}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export const viewers: ViewerAdapter[] = [
  {
    id: "pptx",
    supports: (mime) =>
      mime ===
      "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    component: PptxViewer,
  },
  {
    id: "pdf",
    supports: (mime) => mime === "application/pdf",
    component: PdfViewer,
  },
  { id: "csv", supports: (mime) => mime === "text/csv", component: CsvViewer },
  {
    id: "markdown",
    supports: (mime) => mime === "text/markdown",
    component: MarkdownViewer,
  },
  {
    id: "html",
    supports: (mime) => mime === "text/html",
    component: WebPageViewer,
  },
];
export function ArtifactViewer(props: ViewerProps) {
  const adapter = viewers.find((viewer) =>
    viewer.supports(props.artifact.mime_type),
  );
  const binaryAdapter = adapter?.id === "pdf" || adapter?.id === "pptx";
  const textual = useMemo(
    () =>
      binaryAdapter ? false : isTextArtifact(props.artifact, props.bytes),
    [binaryAdapter, props.artifact, props.bytes],
  );
  const matched =
    adapter && (binaryAdapter || textual)
      ? adapter.component
      : undefined;
  const language = codeLanguage(props.artifact);
  const Viewer =
    matched ??
    (textual
      ? language === "plaintext"
        ? TextViewer
        : CodeViewer
      : undefined);
  return Viewer ? (
    <Suspense fallback={<Loading label="Loading viewer…" />}>
      <Viewer {...props} />
    </Suspense>
  ) : (
    <p className="p-4 text-sm">
      Preview unavailable for this file type. Download the original file to open
      it.
    </p>
  );
}
