SYNTHETIC FIXTURES. Nothing in this directory is shipped, installed or
executed, and nothing here talks to PyPI. Every file is a hand-written stand-in
for one answer an index might give `tools/verify_release_slot.py`.

The project they describe does not exist. It is named `elohim_release_slot.fixture`
in the pyproject below, and stored on disk under its PEP 503 normalised form
`elohim-release-slot-fixture`, so that a check which forgot to normalise the name
would look for a directory that is not there and fail loudly instead of quietly
matching. Its version is 9.9.9, chosen to be unreachable in a real release, and
deliberately NOT the repository's real version: a fixture that named 0.3.0 would
go stale and invert the moment `pyproject.toml` is bumped, and a gate whose
control has rotted is worse than a gate with no control.

Each subdirectory below is one index, and the tool is pointed at it with
`--index-url file://.../<subdirectory>`:

| subdirectory | what the index answers | what it must make the tool do |
|---|---|---|
| `taken` | a real project holding 9.9.9 | exit 1, refusing the release |
| `free` | a real project holding only 9.8.8 | exit 0, allowing the release |
| `malformed` | json with no `releases` map | exit 2, refusing to guess |
| `challenge` | an HTTP 200 that is html, not json | exit 2, refusing to guess |

`challenge` is the one that is not hypothetical. PyPI answers
`https://pypi.org/project/<name>/` with HTTP 200 and a "Client Challenge" page
for names that do not exist, which is recorded in `docs/PUBLISHING.md`. This
directory exists so that the refusal has a committed shape to be tested against,
rather than resting on a sentence in a docstring.