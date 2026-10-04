# Security Policy

## What this project is, and what it is not

ELOHIM is a set of agent skills that run a local measurement and refuse to
pass if anything moved. It is **not** a sandbox, a secret store, or a trust
boundary.

## The honest limit of the pin

Each `ledger.json` records the SHA-256 and byte count of its instrument. That
makes accidental drift impossible: edit the instrument without updating the
ledger and the gate fails with both hashes.

It is **not** protection against a hostile edit. Anyone can satisfy the pin by
editing `ledger.json` too. The protection is **integrity by visibility** — 103
pinned facts, 53 traps re-derived by independent code, and byte-identical
mirrors mean any edit has to be made consistently in several places, in public,
in the commit history, and it is reviewable there. Read the diff, not the
badge.

Nothing here executes untrusted input, reaches the network, or installs
anything. The hygiene lint enforces the standard-library-only rule, and
`install.sh` runs the *installed copy's own gate* rather than trusting the
file it just copied.

## Supported versions

The tip of `main` is the only supported version. There are no release tags and
no backport policy.

## Reporting a vulnerability

Open a **private** security advisory:

> Security tab → Report a vulnerability

Please do not file a public issue for a vulnerability. Include the commit SHA,
the skill name, and the command you ran.

## What counts as a vulnerability here

- an instrument that passes its gate with a modified instrument
- a trap that can no longer fail
- a `check_text` false negative — a shipped text file carrying an artefact of
  its authoring that the lint does not catch: a word the log-sanitising shell
  rewrote in place, an unresolved merge conflict marker left by a merge, or a
  real contributor's home directory left in the text
- a path in the tree that escapes its skill directory

## What does not

- the pin being satisfiable by editing both files. That is a known, documented
  property, not a bug. See above.
- a measurement disagreeing with published literature. If the maths is wrong,
  open an issue and cite the source.
- a promoted fact whose `claim` sentence reads as a rounding of its `expect`.
  That is deliberate. If a claim asserts the *opposite* of its pinned value,
  that **is** a bug and we want it.
