import { tool } from "@opencode-ai/plugin"
import { existsSync, readFileSync, readdirSync } from "node:fs"
import { spawn } from "node:child_process"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = resolve(HERE, "..", "..")
const SKILLS_DIR = process.env.ELOHIM_SKILLS_DIR ?? join(REPO_ROOT, "skills")
const HARNESS = "elohim-harness"
const GATE_TIMEOUT_MS = 600_000

function pythonExecutable() {
  if (process.env.ELOHIM_PYTHON) return process.env.ELOHIM_PYTHON
  return process.platform === "win32" ? "python" : "python3"
}

function skillNames() {
  if (!existsSync(SKILLS_DIR)) return []
  return readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name !== HARNESS)
    .map((entry) => entry.name)
    .filter((name) => existsSync(join(SKILLS_DIR, name, "ledger.json")))
    .sort()
}

function runGate(skillDir) {
  return new Promise((resolvePromise) => {
    const child = spawn(
      pythonExecutable(),
      [join(skillDir, "scripts", "elohim_run.py"), "--json"],
      { cwd: skillDir, env: process.env },
    )
    let out = ""
    let err = ""
    child.stdout.on("data", (chunk) => (out += chunk))
    child.stderr.on("data", (chunk) => (err += chunk))
    const timer = setTimeout(() => child.kill("SIGKILL"), GATE_TIMEOUT_MS)
    child.on("close", (code) => {
      clearTimeout(timer)
      resolvePromise({ code: code ?? -1, out, err })
    })
  })
}

function summarise(skill, raw) {
  const failedFacts = []
  let parsed = null
  try {
    parsed = JSON.parse(raw)
  } catch {
    return {
      skill,
      verdict: "UNPARSEABLE",
      error: "the gate did not emit JSON on stdout",
      stdoutTail: raw.slice(-1200),
    }
  }
  for (const fact of parsed.facts ?? []) {
    if (fact.status !== "verified") failedFacts.push(fact.id)
  }
  return {
    skill,
    verdict: parsed.verdict,
    instrument: parsed.instrument,
    instrumentSource: parsed.instrument_source,
    instrumentPin: parsed.instrument_pin?.status,
    expectedSha256: parsed.instrument_pin?.expected_sha256?.slice(0, 16),
    actualSha256: parsed.instrument_pin?.actual_sha256?.slice(0, 16),
    trapsHeld: (parsed.traps ?? []).filter((t) => t.pass).length,
    trapsTotal: (parsed.traps ?? []).length,
    failedFacts,
    hygieneFindings: (parsed.hygiene?.findings ?? []).map((f) => `${f.file ?? f.kind} ${f.kind} ${f.detail}`),
    seal: parsed.seal,
  }
}

export const elohim_gate = tool({
  description:
    "Run the ELOHIM gate for a skill: verify the instrument checksum pin, the fact ledger against a fresh measurement, the trap suite, and source hygiene. Returns a typed verdict rather than prose.",
  args: {
    skill: tool.schema
      .string()
      .optional()
      .describe("Skill directory name under skills/. Omit to run every skill that owns a ledger."),
  },
  async execute(args) {
    const names = args.skill ? [args.skill] : skillNames()
    if (names.length === 0) {
      return { skills: [], error: `no ledger-bearing skill found under ${SKILLS_DIR}` }
    }
    const results = []
    for (const name of names) {
      const skillDir = join(SKILLS_DIR, name)
      if (!existsSync(join(skillDir, "scripts", "elohim_run.py"))) {
        results.push({ skill: name, verdict: "MISSING_GATE", error: `no scripts/elohim_run.py in ${skillDir}` })
        continue
      }
      const run = await runGate(skillDir)
      results.push(summarise(name, run.out))
    }
    const failing = results.filter((r) => r.verdict !== "PASS")
    return {
      skills: results,
      verdict: failing.length === 0 ? "PASS" : "FAIL",
      failing: failing.map((r) => r.skill),
    }
  },
})

export default elohim_gate
