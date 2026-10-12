import { readFile, stat, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";

const sourceConfigPath = "/input/dbhub.toml";
const liveConfigPath = "/tmp/dbhub.toml";

async function readSourceConfig() {
	for (;;) {
		try {
			const before = await stat(sourceConfigPath, { bigint: true });
			const content = await readFile(sourceConfigPath);
			const after = await stat(sourceConfigPath, { bigint: true });
			if (before.mtimeNs === after.mtimeNs && before.size === after.size) {
				return {
					content,
					version: `${after.mtimeNs}:${after.size}`,
				};
			}
		} catch {
			// The backend may not have created the shared config yet.
		}
		await new Promise((resolve) => {
			setTimeout(resolve, 250);
		});
	}
}

const initialConfig = await readSourceConfig();
await writeFile(liveConfigPath, initialConfig.content, { mode: 0o600 });

const child = spawn(
	process.execPath,
	["/app/dist/index.js", ...process.argv.slice(2)],
	{
		stdio: "inherit",
	},
);

let sourceVersion = initialConfig.version;
let checking = false;

async function relayConfigChange() {
	if (checking) return;
	checking = true;
	try {
		const nextConfig = await readSourceConfig();
		if (nextConfig.version !== sourceVersion) {
			await writeFile(liveConfigPath, nextConfig.content, { mode: 0o600 });
			sourceVersion = nextConfig.version;
		}
	} catch (error) {
		console.error("DBHub config relay failed:", error);
	} finally {
		checking = false;
	}
}

const interval = setInterval(() => {
	void relayConfigChange();
}, 500);
interval.unref();

for (const signal of ["SIGINT", "SIGTERM"]) {
	process.on(signal, () => {
		child.kill(signal);
	});
}

child.on("exit", (code, signal) => {
	clearInterval(interval);
	if (signal) {
		process.kill(process.pid, signal);
		return;
	}
	process.exit(code ?? 1);
});
