---
name: elohim-fixture
description: A deliberately duplicated skill name used only as a negative control for tools/verify_skill_roots.py.
license: MIT
---

# Do not load this

This file exists so that `tools/verify_skill_roots.py` can be run against a tree
that is known to contain the defect it hunts, on every CI run.

Two project-local roots inside this fixture directory each hold a skill named
`elohim-fixture`, which is exactly the condition the gate refuses. Nothing ever
loads these skills: the name is not a real skill, the directory is not one of
opencode's six roots when the repository is checked out normally, and
`npx skills add` walks container directories at most three levels deep from the
repository root, while this fixture sits five or more.

Delete this and the fixture check goes red with "expected a duplicate, found
none" — which is the point. A negative control that cannot fail is not evidence
that anything is checked.
