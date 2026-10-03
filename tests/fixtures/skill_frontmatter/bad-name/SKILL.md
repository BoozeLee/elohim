---
name: not-the-directory-name
description: A fixture whose declared name disagrees with the directory holding it.
license: MIT
---

# Do not load this

opencode requires that `name` "Match the directory name that contains
`SKILL.md`". Nothing warns when it disagrees: the file loads under a name nothing
on disk matches, and the mismatch surfaces as a skill that cannot be addressed,
or not found at all.

This file is that mismatch on purpose, for
`tools/verify_skill_frontmatter.py` to find. The fix is to make the two agree --
which one you change is a decision, not a lint fix, so the tool reports both
values rather than choosing.
