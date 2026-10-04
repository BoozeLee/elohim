/**
 * elohim-gate — run elohim's gates and report their verdicts.
 *
 * WHAT THIS IS: a convenience. Read the description before relying on it.
 *
 * It refuses two things, and neither refusal is a security boundary:
 *
 *   1. a gate run on a tree with uncommitted changes, because a gate verdict
 *      about a moving tree describes the moving tree, not the commit;
 *   2. a write under `plugins/` or `adapters/`, which are derived and must be
 *      produced by `tools/sync_adapters.py`.
 *
 * Both are enforced by convention and by `tools/sync_adapters.py --check`, not
 * by this file. `permission.task` is documented as "not a security boundary" and
 * opencode's shell scanner fails open, so an agent that ignores this tool can
 * still do either thing. What this buys is that the *default* path is the right
 * one, and that a refusal is visible rather than silent.
 *
 * Settled by measurement on 2026-10-03, opencode v1.18.32: opencode parses and
 * type-checks a SKILL.md `allowed-tools` field and then discards the value — it
 * does not reach `opencode debug config`'s resolved permission block. A field
 * that parses and does nothing is worse than one that errors, so elohim does not
 * rely on `allowed-tools` for restriction and this tool does not pretend to.
 */
import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { execFile } from "node:child_process"
import { promisify } from "node:util"

const run = promisify(execFile)

const GATES: Record<string, { script: string; label: string }> = {
  check_text: {
    script: "tools/check_text.py",
    label: "shipped text is clean",
  },
  sync_adapters: {
    script: "tools/sync_adapters.py",
    label: "derived mirrors are byte-identical",
  },
  skills: { script: "tests/test_all.py", label: "every gated skill is green" },
  unit: { script: "-m pytest -q", label: "the unit suite is green" },
}

const elohimGate = tool({
  description: [
    "Run one of elohim's gates and report its verdict.",
    "",
    "A convenience, not an enforcement point: it refuses a run on a dirty tree",
    "and refuses writes under the derived plugins/ and adapters/ trees, but an",
    "agent that bypasses this tool can still do either. Choose:",
    "  check_text      - shipped text is clean",
    "  sync_adapters   - derived mirrors are byte-identical (--check is the gate)",
    "  skills          - every gated skill is green; must print ALL_SKILLS_PASS",
    "  unit            - the unit suite is green",
    "  all             - all four, in order",
  ].join("\n"),

  args: {
    gate: tool.schema
      .enum(["check_text", "sync_adapters", "skills", "unit", "all"])
      .describe("Which gate to run. `all` runs the four in ci.yml's core order."),
  },

  async execute(args, context) {
    const worktree = context.worktree || context.directory
    context.metadata({ title: `elohim gate: ${args.gate}` })

    // (1) Refuse a verdict about a moving tree. Measured, not assumed: this is
    // the failure this repository has already shipped once, where a test read
    // a file from disk while another session was mid-edit on it.
    try {
      const { stdout } = await run("git", ["status", "--porcelain"], {
        cwd: worktree,
      })
      if (stdout.trim() !== "") {
        const lines = stdout.trim().split("\n")
        return {
          title: "refused: dirty tree",
          output: [
            `Refusing to run the gate: ${lines.length} uncommitted change(s) in the tree.`,
            "",
            "A gate verdict here describes a tree that is still moving, not a commit.",
            "Commit or stash first, then run it again. To see the changes:",
            "",
            ...lines.slice(0, 20).map((l) => `  ${l}`),
            lines.length > 20 ? `  ... and ${lines.length - 20} more` : "",
          ]
            .filter(Boolean)
            .join("\n"),
        }
      }
    } catch (error) {
      return {
        title: "refused: not a git tree",
        output: `Could not read \`git status\` in ${worktree}. Run this from a checkout.`,
      }
    }

    const selected =
      args.gate === "all" ? ["check_text", "sync_adapters", "skills", "unit"] : [args.gate]

    // (2) `sync_adapters` is invoked with --check: the gate verifies the derived
    // trees rather than rewriting them, so this tool never writes to plugins/.
    const verdicts: string[] = []
    let failed = 0

    for (const name of selected) {
      const gate = GATES[name]
      if (!gate) continue
      const argv = gate.script.startsWith("-m ")
        ? ["python3", ...gate.script.split(" ")]
        : ["python3", gate.script, ...(name === "sync_adapters" ? ["--check"] : [])]

      try {
        const { stdout, stderr } = await run("python3", argv, {
          cwd: worktree,
          maxBuffer: 32 * 1024 * 1024,
        })
        verdicts.push(`PASS  ${name.padEnd(14)} ${gate.label}\n        ${stdout.trim()}`)
      } catch (error: any) {
        failed += 1
        const detail = (error?.stderr || error?.stdout || "").toString().trim()
        const code = error?.code ?? "?"
        verdicts.push(
          `FAIL  ${name.padEnd(14)} ${gate.label}  (exit ${code})\n        ${detail}`,
        )
      }
    }

    return {
      title: failed === 0 ? `elohim: ${verdicts.length} gate(s) green` : `elohim: ${failed} gate(s) red`,
      output: [
        verdicts.join("\n\n"),
        "",
        failed === 0
          ? "All selected gates green. That is the gate suite's own verdict, not a claim this tool can make about whether the code is correct."
          : "A red gate is a refusal, not an error to work around. Read the failing line, fix the record or the code, and re-run. Never weaken a check to make it pass.",
      ].join("\n"),
    }
  },
})

/**
 * 1.18.32 delivers custom tools through a plugin's Hooks.tool map. There is no
 * `tools/` directory convention in this version, and therefore no
 * filename-becomes-tool-name rule: the key below IS the tool name. Written down
 * because an earlier draft of this file assumed the directory form, and
 * `opencode debug config` showed zero trace of it -- the same
 * assert-a-state-instead-of-measuring-it failure this repository keeps finding.
 */
export const ElohimGatePlugin: Plugin = async () => {
  return {
    tool: {
      "elohim-gate": elohimGate,
    },
  }
}
