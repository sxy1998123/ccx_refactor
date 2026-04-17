import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const electronVitePackageJson = require.resolve("electron-vite/package.json");
const electronViteBin = path.join(path.dirname(electronVitePackageJson), "bin", "electron-vite.js");
const args = process.argv.slice(2);
const knownPrefixes = ["[node]", "[python]"];

delete process.env.ELECTRON_RUN_AS_NODE;

function hasKnownPrefix(line) {
  return knownPrefixes.some((prefix) => line.startsWith(prefix));
}

function createLinePrefixer(prefix, stream) {
  let buffered = "";

  return {
    write(chunk) {
      buffered += chunk.toString("utf8");
      const lines = buffered.split(/\r?\n/);
      buffered = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.trim()) {
          continue;
        }
        stream.write(hasKnownPrefix(line) ? `${line}\n` : `${prefix} ${line}\n`);
      }
    },
    flush() {
      if (buffered.trim()) {
        stream.write(hasKnownPrefix(buffered) ? `${buffered}\n` : `${prefix} ${buffered}\n`);
      }
      buffered = "";
    },
  };
}

const child = spawn(process.execPath, [electronViteBin, ...args], {
  stdio: ["inherit", "pipe", "pipe"],
  env: process.env,
  shell: false,
});

const stdoutPrefixer = createLinePrefixer("[node]", process.stdout);
const stderrPrefixer = createLinePrefixer("[node]", process.stderr);

child.stdout?.on("data", (chunk) => stdoutPrefixer.write(chunk));
child.stderr?.on("data", (chunk) => stderrPrefixer.write(chunk));

child.on("exit", (code, signal) => {
  stdoutPrefixer.flush();
  stderrPrefixer.flush();

  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
