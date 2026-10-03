---
name: bad-description
description: Use when checking the linter note: this description is deliberately broken
license: MIT
---

# Do not load this

The `description` above carries a bare `: ` between `note` and `this`. A strict
YAML parser reads that as a nested mapping and throws
`Nested mappings are not allowed in compact mappings`, and
`vercel-labs/skills#1282` records what happens next: `discoverSkills` "silently
omits any skill whose SKILL.md YAML frontmatter fails to parse. No warning, no
error -- the skill is simply missing from `--list` output".

So this file is a skill that does not exist, committed on purpose, for
`tools/verify_skill_frontmatter.py` to find. Quoting the value would fix it --
`description: "Use when ... note: this ..."` is one string -- which is exactly
the fix the tool's message tells you to make.
