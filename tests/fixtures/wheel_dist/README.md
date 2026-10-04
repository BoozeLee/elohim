# Fixtures for `tools/verify_wheel.py --dist`

Synthetic. Nothing in this directory is shipped, built, installed, or uploaded,
and no file here is a real wheel: the three `*.whl` files are zero bytes and
exist only so the directory listing they sit in has the shape the gate is
supposed to reason about.

They feed `tests/test_wheel_dist.py`, which drives `verify_wheel.py`'s wheel
selection offline. Three shapes, one per refusal the gate owes a reason for:

| Directory | Holds | What the gate must say |
|---|---|---|
| `no_wheel/` | a `NOTE.md` and nothing else | one wheel was expected and zero were found |
| `two_wheels/` | `elohim-0.3.0-…whl`, `elohim-0.3.1-…whl` | one wheel was expected and two were found, by name |
| `one_wheel/` | `elohim-0.3.0-…whl`, zero bytes | one wheel was found and it is not a readable zip |

`no_wheel/` is not an empty directory because git does not track empty
directories, and a `dist/` holding only an sdist is the realistic version of the
same refusal.

The versions in the names are the ones this repository published while the
fixtures were written. They are decoration: the gate reads filenames only to
report what it found, and every assertion below is about counts and shapes. A
fixture whose value had to be kept in step with `pyproject.toml` would rot into
a vacuous control the next time the version was bumped.