# Publishing, and what to do when it refuses

How to cut a release of elohim, and — more usefully — what the failure looks
like when a release does not happen, because that is the part nobody has in
front of them at the moment they need it.

Everything numeric in this file was measured on 2026-10-03, the day `0.3.0` was
published. The commands are the ones that ran. Where a number is a decision
rather than a measurement, it says so.

## The arrangement

`.github/workflows/publish.yml` is `workflow_dispatch`-only. **A tag push
publishes nothing.** Every release is a person deciding to do it:

```bash
gh workflow run publish.yml --ref main
```

This is deliberate. A tag-triggered publish was put to the project's judge and
declined at probability 0.29: publishing should be something a person does on
purpose, and an automatic trigger on a tag removes the last moment at which a
human can notice the artefact is wrong.

The cost of that decision is the subject of the second half of this file.

## Cutting a release

**1. Merge the release branch.** The workflow that publishes should be the one
that has run, not the one that is about to.

**2. Check the name, immediately before you dispatch — not now.**

```bash
curl -s https://pypi.org/pypi/elohim/json
```

`{"message": "Not Found"}` means the name is free.

Use the JSON API. **Do not use the web page for this.** `https://pypi.org/project/elohim/`
returns **HTTP 200 for names that do not exist**, because PyPI serves an
anti-scraping "Client Challenge" page with a 200 status. An availability check
written against that status code reports a free name as taken, and one written
against the page body reports a taken name as free. Both directions wrong, from
the same URL.

The control that makes the JSON API trustworthy: `requests` and `pytest` must
return real `info` from the same endpoint, or it is not answering and its
`Not Found` means nothing.

**The workflow now repeats this check itself, and refuses before it builds.**
`tools/verify_release_slot.py` reads the version out of `pyproject.toml` and asks
the same JSON API whether the index already holds it. If it does, the run stops
with exit 1 and names the number to bump; if the index cannot be read at all it
stops with exit 2 rather than guessing, because "the index did not answer" is not
"the slot is free". So the manual check below is for deciding *whether* to
dispatch. The one in the workflow is for stopping a dispatch that should not have
happened.

**3. Dispatch.** No `-f dry_run=true` — that flag is what makes it *not*
upload. With the flag absent the upload step runs.

**4. Read the run back.** Check that the `publish to PyPI` step is `success` and
not `skipped`. Those two look identical in a green badge and mean opposite
things: `skipped` is a dry run, `success` is an upload. Read it by name rather
than by position — a step added anywhere above it renumbers everything below,
and this file has been wrong about that number before.

Two steps sit above the upload and can stop a run before anything leaves this
repository: `the version being offered is not already released`, and `the wheel
about to be uploaded installs and its API runs`. Red on either means **nothing was
uploaded**, which is the outcome you wanted rather than a failure to retry. Fix
the cause — usually a version bump, or a packaging defect — and dispatch again.
There is no in-between state to clean up: the upload is one step, and it is the
first one after both gates.

## When it refuses

This is the part worth keeping.

The publish step exchanges an OIDC identity token for a short-lived PyPI
upload token. PyPI matches that token against a trusted publisher you registered
by hand, against three strings: **repository owner**, **repository name**, and
**environment name**. If any of the three drifts, the match fails and the run
goes red.

The error names the mismatching field itself. This is the whole message:

```text
##[error]Trusted publishing exchange failure:
Token request failed: the server refused the request for the following reasons:

* `invalid-publisher`: valid token, but no corresponding publisher
  (Publisher with matching claims was not found)

The claims rendered below are **for debugging purposes only**.

* `repository`: `BoozeLee/elohim`
* `repository_owner`: `BoozeLee`
* `repository_owner_id`: `96494827`
* `workflow_ref`: `BoozeLee/elohim/.github/workflows/publish.yml@refs/heads/main`
* `job_workflow_ref`: `BoozeLee/elohim/.github/workflows/publish.yml@refs/heads/main`
* `ref`: `refs/heads/main`
* `environment`: `pypi`
```

Compare those against what you registered. The two claims that are *not* printed
— the workflow filename PyPI expects and the pending project name — are
`publish.yml` and `elohim`.

### What it costs, measured

Two real occurrences, both on 2026-10-03, both the same cause:

| | |
|---|---|
| Run `37111874910` | red in **21 seconds** |
| Run `37112485344` | red in **19 seconds** |
| Cause | publisher held `BoozeLee/Elohim`; the claim is `BoozeLee/elohim` |
| Uploaded | **nothing** — the failure is at token exchange, before any transfer |
| Name consumed | **no** — a failed attempt does not reserve or claim anything |
| Break to fixed | about six minutes, including re-registration |

The failure cannot half-publish. It cannot consume the name. It cannot leave a
truncated file on the index. And it cannot be diagnosed by guessing, because the
error prints the exact strings PyPI is comparing. One capital letter in a field
PyPI renders back to you in a table was the entire defect, and it was found
because the error said so.

**The pending publisher's fields are not reliably editable in place.** Deleting
the publisher and adding a fresh one is what actually changed the stored value.
An edit that appeared to save did not.

### Re-registering

Go to <https://pypi.org/manage/account/publishing/> — the account sidebar, not
a project's. For a project that does not exist yet this registers a *pending*
publisher, which is converted to a permanent one on first successful use.

| Field | Value |
|---|---|
| PyPI project name | `elohim` |
| Owner | `BoozeLee` |
| Repository name | `elohim` |
| Workflow filename | `publish.yml` |
| Environment name | `pypi` |

Two fields catch people:

- **The repository name is lowercase.** `elohim`, not `Elohim`. PyPI matches the
  OIDC claim exactly and the claim is lowercase. It is also the field PyPI
  displays capitalised back to you, so the table can look right while the
  stored value is wrong.
- **The workflow filename is the bare basename.** `publish.yml`, not
  `.github/workflows/publish.yml`.

The GitHub environment named here must exist. `pypi` was never created by hand:
GitHub auto-created it at `2026-10-03T08:00:13Z`, the first time a job
declaring `environment: pypi` ran, with no protection rules and no branch
restriction — so the publish job never waits for a manual approval. Do not add
required reviewers to it; a first publish with one person on the project would
block waiting for a second.

## The standing cost, and when a gate gets built

The publisher is configured on PyPI's side against three strings this repository
cannot read. There is no unauthenticated API for a user's publishers and no
credential for one on any host this work is done from. So a rename can sit
undetected for a long time, and the only signal arrives when someone tries to
publish.

**What was decided on 2026-10-03**, after two rounds of consultation that did
*not* reach the project's decision threshold:

| Round | Leading answer | P | Confidence |
|---|---|---|---|
| 1 | add nothing | 0.72 | 0.62 |
| 2 | add nothing | 0.65 | 0.54 |

Threshold is 0.78 on both. The judge led on "add nothing" twice and approved
nothing; the case for a gate held at 0.28 and then 0.26, a minority that did not
go to zero. The decision recorded is therefore **both halves, separated by what
they cost**:

1. **This file is the cheap half.** It exists now, before anything breaks, so
   the six-minute fix is a lookup rather than a reconstruction under pressure.
   No new code, and no new pinned string that can itself go stale.
2. **The gate is deferred to a trigger, and the trigger is written down.** Build
   a push-time drift gate when — and only when — a rename happens that a human
   did not knowingly cause: a repository transfer, an organisation rename, a
   collaborator's settings change, or the repository being recreated under the
   same short name. In every observed case so far the person changing the string
   already knew, because they had just typed it.

A push-time gate, when it is built, can only catch two things: that the
environment named in `publish.yml` still exists in the repository, and that the
git remote's full name still matches a recorded value. It **cannot** detect
PyPI-side drift, which is the failure that has actually occurred, and it would
introduce a recorded owner/repository string — a pinned number in a file, which
is the shape that goes quietly false while every test is green, and which this
repository has already shipped twice.

The honest reason the gate is not built yet: one occurrence has been observed,
it was a human typo, and it was caught in under half a minute by an error
message that named the field. A gate justified by one typo is a gate justified
by a guess. When it is justified by evidence, the evidence will be a rename
nobody intended — and this file is the record of that decision.
