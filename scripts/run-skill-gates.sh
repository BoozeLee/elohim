#!/usr/bin/env bash
# Run the exit-code gates in this repository, in the order CI runs them.
#
# Every gate here resolves its own repository from its own file path, so the
# meta-gate cannot drive them with an argument -- it copies each one into a
# fixture and runs it there. That is the `relocated` invocation in
# `.gate-manifest`, and it is the reason this file exists rather than a
# Makefile target: the gates are Python, they are already run individually by
# ci.yml and matrix.yml, and one list that both CI and a developer can run is
# worth more than a second place the steps are written down.
#
# Self-tests run before audits. An audit performed by an instrument that cannot
# fail proves nothing about the tree.
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

gate_names=(
  "meta-gate self-test"
  "frontmatter self-test"
  "skill-roots self-test"
  "meta-gate audit"
  "frontmatter audit"
  "skill-roots audit"
)
# The --expect-findings steps are the committed negative controls, invoked
# exactly as matrix.yml invokes them. Both need the fixture named: without
# --skill-root / --root they audit the real tree, find nothing, and --expect-
# findings correctly reports that the fixture stopped reproducing its defect --
# which is how this first version failed, by running a control against the
# wrong subject.
gate_cmds=(
  "scripts/check-gates-are-honest.sh --self-test"
  "tools/verify_skill_frontmatter.py --skill-root tests/fixtures/skill_frontmatter --expect-findings"
  "tools/verify_skill_roots.py --root tests/fixtures/skill_roots --expect-findings"
  "scripts/check-gates-are-honest.sh"
  "tools/verify_skill_frontmatter.py"
  "tools/verify_skill_roots.py"
)

if [ "${1:-}" = "--list" ]; then
  printf '%s\n' "${gate_names[@]}"
  exit 0
fi

failures=0
for i in "${!gate_names[@]}"; do
  printf '\n=== %s ===\n' "${gate_names[$i]}"
  # Not `if ! cmd`: that would make $? the status of the negation.
  ${gate_cmds[$i]}
  status=$?
  if [ "$status" -ne 0 ]; then
    case "$status" in
      1) why="findings" ;;
      2) why="inconclusive -- nothing was verified" ;;
      *) why="unexpected exit" ;;
    esac
    printf '  FAILED: %s (exit %s -- %s)\n' "${gate_names[$i]}" "$status" "$why" >&2
    failures=$((failures + 1))
  fi
done

printf '\n'
if [ "$failures" -ne 0 ]; then
  printf '%s of %s gate(s) failed\n' "$failures" "${#gate_names[@]}" >&2
  exit 1
fi
printf 'all %s gate(s) passed\n' "${#gate_names[@]}"
