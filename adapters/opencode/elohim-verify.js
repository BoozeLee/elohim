// ELOHIM gate adapter for opencode.
//
// Two jobs, both deliberately outside the measurement path:
//   1. point ELOHIM_SCRIPT at the bundled, checksum-pinned instrument;
 //   2. run the three-leg gate when a session goes idle, and complain only
//      when the verdict is not PASS.
//
// Copy this file into a project's .opencode/plugins/ directory to enable it,
// or add the repository to the "plugin" array in opencode.json.
// It never writes, never installs, and never reaches the network.

import { spawn } from "node:child_process"
import { existsSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))

// adapters/opencode -> repo root;  also correct when copied to <root>/.opencode/plugins/.
const REPO_ROOT = resolve(HERE, "..", "..")
const DEFAULT_SKILL = join(REPO_ROOT, "skills", "elohim")

const IDLE_MIN_INTERVAL_MS = 5 * 60 * 1000

function skillDir(options) {
  const fromOptions = options &&  options.elohim &&  options.elohim.skillDir
  if (fromOptions) return resolve(String(fromOptions))
  const fromEnv = process.env.ELOHIM_SKILL_DIR
  if (fromEnv) return resolve(fromEnv)
  return DEFAULT_SKILL
}

function gateScript(dir) {
  return join(dir, "scripts", "elohim_run.py")
}

function instrument(dir) {
  return join(dir, "instrument", "summoning_shard.py")
}

function pythonExecutable() {
  if (process.env.ELOHIM_PYTHON) return process.env.ELOHIM_PYTHON
  return process.platform === "win32" ? "python" : "python3"
}

function runGate(dir, done) {
  const script = gateScript(dir)
  if (!existsSync(script)) {
    done({ ran: false, reason: `no gate at ${script}` })
    return
  }
  const child = spawn(pythonExecutable(), [script], {
    cwd: dir,
    env: { ...process.env, ELOHIM_SCRIPT: instrument(dir) },
    stdio: ["ignore", "pipe", "pipe"],
  })
  let out = ""
  child.stdout.on("data", (d) => (out += d.toString()))
  child.stderr.on("data", (d) => (out += d.toString()))
  child.on("error", (err) => done({ ran: false, reason: String(err) }))
  child.on("close", (code) => done({ ran: true, code, output: out.trim() }))
}

export const ElohimVerify = async (_input, options = {}) => {
  const dir = skillDir(options)
  let lastRun = 0

  return {
    tool: {},

    "shell.env": async () => ({
      ELOHIM_SCRIPT: instrument(dir),
      ELOHIM_SKILL_DIR: dir,
    }),

    event: async ({ event }) => {
      if (!event ||  event.type !== "session.idle") return
      const now = Date.now()
      if (now - lastRun < IDLE_MIN_INTERVAL_MS) return
      lastRun = now
      runGate(dir, ({ ran, code, reason, output }) => {
        if (!ran) {
          console.log(`[elohim] gate skipped: ${reason}`)
          return
        }
        if (code === 0) return
        console.log(`[elohim] gate FAILED (exit ${code})\n${output}`)
      })
    },
  }
}

export default ElohimVerify
