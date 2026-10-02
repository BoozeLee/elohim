#!/usr/bin/env python3
"""Prove the installed wheel can run the Python API, not just the console script.

The claim this exists to check is in pyproject.toml: "The gate resolves
everything from Path(__file__), so the installed copy runs anywhere." It was
true of the console script and false of the API. cli.py resolved the instrument
skills by searching the packaged copy first and then walking up to a checkout;
seven reads in census.py and mutation.py went straight to REPO / "skills",
which inside a wheel is site-packages/skills -- a directory that does not exist,
because the build backend places the instruments at elohim_gate/_skills/ and
nothing puts them back at the top level. A wheel install of this package raised
FileNotFoundError from inside shutil.copytree, naming a path the caller had
never heard of, one level below the package data that was sitting there the
whole time. pip install elohim is the distribution form E3 depends on and an
external caller is the only thing that closes E1's third clause, so the one
thing nobody had done was install the thing and call it.

The check is deliberately not a fabricated directory layout. Building an
in-process fake that mimics site-packages would be testing the fake; building
the real artifact and installing it into a real venv is what a user gets, and
it also catches packaging metadata errors that no in-process test can see.

Every probe runs with its working directory outside the source checkout. That
is not tidiness: the resolver walks up from its own file looking for a checkout,
and a probe run from inside the repo would find skills/ by a path that does not
exist for anyone who pip-installed the package.

Probes are chosen to be cheap. Nothing here runs a full census -- that is 1,679
mutation sites -- because this gate runs on every push and a gate nobody waits
for is a gate that gets deleted. The two copy sites that a full census would
reach are covered directly instead: build_population for the ledger reads, and a
job naming a nonexistent skill for the second copytree, which returns SKIPPED
before it would run anything.

Stdlib only, like every tool in this repository. Invoked from CI as a separate
job so it runs in parallel with the unit gates instead of extending them.
"""

import ast
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PKG = "elohim_gate"

PROBE = r'''
import json, os, sys
from pathlib import Path

from elohim_gate import census, mutation

# argv[1] is an empty directory used to force the "nothing resolves" refusal.
# argv[2] is the checkout, for the probe that proves ELOHIM_REPO still wins.
CHECKOUT = Path(sys.argv[2])

out = {}

def probe(name, fn):
    try:
        out[name] = {"ok": True, "value": fn()}
    except BaseException as exc:
        out[name] = {"ok": False, "error": type(exc).__name__ + ": " + str(exc)}

# 1. The resolver returns a real tree holding the instrument skills.
def skills_root():
    root = mutation.skills_root()
    if not root.is_dir():
        raise AssertionError("skills_root() returned a non-directory: " + str(root))
    return str(root)
probe("skills_root", skills_root)

# 2. The instrument runner resolves, instead of surfacing later as an opaque
#    "can't open file" from a child process.
def harness_path():
    p = mutation.harness_path()
    if not p.is_file():
        raise AssertionError("harness_path() returned a non-file: " + str(p))
    return str(p)
probe("harness_path", harness_path)

# 3. ELOHIM_REPO still wins, which is what makes an external caller able to
#    point the gate at a checkout of a different revision.
def env_override_wins():
    saved = os.environ.get("ELOHIM_REPO")
    try:
        os.environ["ELOHIM_REPO"] = str(CHECKOUT)
        root = mutation.skills_root()
        if Path(root) != CHECKOUT / "skills":
            raise AssertionError(
                "ELOHIM_REPO was set to %s but skills_root() returned %s"
                % (CHECKOUT, root))
        return "ok"
    finally:
        if saved is None:
            os.environ.pop("ELOHIM_REPO", None)
        else:
            os.environ["ELOHIM_REPO"] = saved
probe("env_override_wins", env_override_wins)

# 4. The ledger reads inside build_population, against a real skill.
def build_population():
    jobs, population = census.build_population(["elohim"])
    if not jobs:
        raise AssertionError("build_population(['elohim']) produced no jobs")
    return "%d job(s), %d operator(s)" % (
        len(jobs), len(population.get("elohim", {})))
probe("build_population", build_population)

# 5. The second copy site, cheaply. one() copies the whole skills tree, reads
#    the ledger through instrument_path, and only then asks for a mutant, so a
#    site index past the end of a real operator returns SKIPPED without running
#    a single mutation. SKIPPED is the honest outcome, not a pass, and the
#    probe asserts exactly that rather than treating it as success.
def unreachable_site_job():
    jobs, _ = census.build_population(["elohim"])
    real = jobs[0]
    job = {"skill": real["skill"], "arm": "forged",
           "operator": real["operator"], "site_index": 10 ** 9,
           "lineno": 0, "site": "<past the end>"}
    row = census.one(job)
    if row.get("outcome") != "SKIPPED":
        raise AssertionError(
            "a site index past the end should report SKIPPED, got %r"
            % (row.get("outcome"),))
    return row["outcome"] + ": " + str(row.get("cause"))[:40]
probe("unreachable_site_job", unreachable_site_job)

# 6. The pristine shard: one copytree plus one real instrument run. This is the
#    only probe that costs anything, and it is the one that proves the copy is
#    of a tree the instrument can actually execute from. It returns
#    (shard_text, error); a populated shard with no error is the only pass,
#    because a None shard is how a broken copy reports itself.
def pristine_shard():
    shard, err = census.pristine_shard("elohim", 3)
    if err is not None:
        raise AssertionError(err)
    if not shard:
        raise AssertionError("pristine_shard returned no shard and no error")
    return "shard of %d bytes" % len(shard)
probe("pristine_shard", pristine_shard)

# 7. Verdict policy is reachable from an install, which is all of E3's
#    acceptance criterion except that the environment is clean. The rows below
#    are a fixture for the summary mapping, not a measurement: what is under
#    test is that gate_verdict's two-level read of the summary and its handoff
#    to mutate.verdict both survive an install. The census itself is measured
#    by tests/test_all.py and nowhere here.
def verdict_policy_reachable():
    rows = [{"arm": "forged", "operator": op, "skill": "elohim",
             "outcome": outcome}
            for op, outcome in (("constant", "CAUGHT"), ("boundary", "EFFECTIVE"),
                                ("identity", "CAUGHT"), ("augmented", "CAUGHT"))]
    summary = census.summarise(rows, len(rows))
    return {"defect_arm_total_n": summary["defect_arm_total"]["n"],
            "verdicts": {str(fo): census.gate_verdict(summary, fo).exit_code
                         for fo in (0.25, 0.5)}}
probe("verdict_policy_reachable", verdict_policy_reachable)

# 8. Refusal control: ELOHIM_REPO pointing nowhere must refuse, loudly and by
#    name, rather than measuring some other tree.
def refuses_bad_override():
    saved = os.environ.get("ELOHIM_REPO")
    try:
        os.environ["ELOHIM_REPO"] = "/nonexistent-elohim-repo"
        try:
            mutation.skills_root()
        except FileNotFoundError as exc:
            if "nonexistent-elohim-repo" not in str(exc):
                raise AssertionError(
                    "refusal did not name the override it rejected: %s" % exc)
            return "refused by name"
        raise AssertionError("a bad ELOHIM_REPO was accepted")
    finally:
        if saved is None:
            os.environ.pop("ELOHIM_REPO", None)
        else:
            os.environ["ELOHIM_REPO"] = saved
probe("refuses_bad_override", refuses_bad_override)

# 9. Refusal control: with no packaged copy and no checkout above it, the error
#    must list what it looked for. A bare "not found" here is the defect this
#    whole change exists to remove.
def refuses_when_nothing_resolves():
    saved_root = mutation._PKG_ROOT
    empty = Path(sys.argv[1])
    try:
        mutation._PKG_ROOT = empty
        try:
            mutation.skills_root()
        except FileNotFoundError as exc:
            if "skills" not in str(exc):
                raise AssertionError(
                    "refusal did not say what it looked for: %s" % exc)
            return "refused, naming candidates"
        raise AssertionError("resolved a skills tree that does not exist")
    finally:
        mutation._PKG_ROOT = saved_root
probe("refuses_when_nothing_resolves", refuses_when_nothing_resolves)

print(json.dumps(out))
'''


def _fail(msg):
    print("verify_wheel: " + msg, file=sys.stderr)
    return 1


def static_check() -> list[str]:
    """No code path may reach the skills tree by dividing REPO by a literal.

    Uses ast rather than a text search, and that is the whole point. The
    resolver's own docstring quotes the pattern it replaced, so grepping for it
    finds the explanation of the fix and calls the fix broken. ast sees only
    expressions: a docstring is a constant, never a division.
    """
    problems = []
    src = Path(__file__).resolve().parent.parent / PKG
    for path in sorted(src.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
                continue
            right = node.right
            if not (isinstance(right, ast.Constant) and right.value == "skills"):
                continue
            left = node.left
            attr = left.attr if isinstance(left, ast.Attribute) else None
            name = left.id if isinstance(left, ast.Name) else None
            if "REPO" in (attr, name):
                problems.append(
                    "%s:%d reads a skills tree off %s; call skills_root()"
                    % (path.name, node.lineno, attr or name))
    return problems


def _run(cmd, cwd, env=None):
    return subprocess.run(
        cmd, cwd=str(cwd), env=env, capture_output=True, text=True)


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    if not (repo / PKG).is_dir():
        return _fail("not run from a checkout: %s has no %s/" % (repo, PKG))

    problems = static_check()
    if problems:
        return _fail("a skills tree is still read off REPO:\n  "
                     + "\n  ".join(problems))
    print("static: no code reads a skills tree off REPO")

    with tempfile.TemporaryDirectory(prefix="elohim-wheel-") as scratch:
        tmp = Path(scratch)
        dist = tmp / "dist"
        # --no-isolation because an isolated build downloads its own backend,
        # which would put a second pinned version in this repository to keep in
        # step with the one pyproject.toml already names.
        build = _run([sys.executable, "-m", "build", "--wheel",
                      "--no-isolation", "--outdir", str(dist)], repo)
        if build.returncode != 0:
            return _fail("wheel build failed:\n" + build.stdout + build.stderr)
        wheels = sorted(dist.glob("*.whl"))
        if len(wheels) != 1:
            return _fail("expected exactly one wheel, got %r"
                         % [w.name for w in wheels])
        print("built: %s (%d bytes)" % (wheels[0].name, wheels[0].stat().st_size))

        # The wheel must ship the instruments inside the package.
        with __import__("zipfile").ZipFile(wheels[0]) as zf:
            names = zf.namelist()
            if not any(n.startswith(PKG + "/_skills/") for n in names):
                return _fail("the wheel contains no %s/_skills/ entries" % PKG)
            if any(n.startswith("skills/") for n in names):
                return _fail(
                    "the wheel contains a top-level skills/, which would shadow "
                    "any other distribution shipping that name")
            if not any(n.endswith("elohim-harness/scripts/harness_run.py")
                       for n in names):
                return _fail("the wheel ships no instrument runner")
            print("contents: %d entries, instruments under %s/_skills/"
                  % (len(names), PKG))

        env_dir = tmp / "env"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        py = env_dir / "bin" / "python"
        if not py.exists():
            py = env_dir / "Scripts" / "python.exe"
        install = _run([str(py), "-m", "pip", "install", "--quiet",
                        "--disable-pip-version-check", "--no-deps",
                        str(wheels[0])], tmp)
        if install.returncode != 0:
            return _fail("wheel install failed:\n" + install.stdout + install.stderr)

        # Outside the checkout, so a parent walk cannot find the source tree.
        cwd = tmp / "elsewhere"
        cwd.mkdir()

        probe_src = tmp / "probe.py"
        probe_src.write_text(PROBE)
        empty = tmp / "empty"
        empty.mkdir()

        run = _run([str(py), str(probe_src), str(empty), str(repo)], cwd)
        if run.returncode != 0:
            return _fail("probe crashed:\n" + run.stdout + run.stderr)

        import json
        try:
            results = json.loads(run.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return _fail("probe printed no result line:\n" + run.stdout
                         + run.stderr)

        failed = []
        for name in sorted(results):
            r = results[name]
            if r["ok"]:
                print("  pass  %-32s %s" % (name, str(r["value"])[:60]))
            else:
                failed.append(name)
                print("  FAIL  %-32s %s" % (name, r["error"]))
        if failed:
            return _fail("%d probe(s) failed: %s" % (len(failed),
                                                     ", ".join(failed)))

        # The code that ran must be the code in this checkout, or the probes
        # above proved something about a stale artifact. Asking the venv for its
        # own purelib matters: sysconfig in this process would answer for the
        # host interpreter and the check would pass against the wrong tree.
        import json
        compare = _run([str(py), "-c",
                        "import importlib, json, sysconfig, sys;"
                        "m = importlib.import_module(%r);"
                        "sys.stdout.write(json.dumps({'file': m.__file__,"
                        " 'purelib': sysconfig.get_paths()['purelib']}))" % PKG],
                       cwd)
        if compare.returncode != 0:
            return _fail("could not import the installed package:\n"
                         + compare.stdout + compare.stderr)
        info = json.loads(compare.stdout)
        installed = Path(info["file"]).resolve()
        purelib = Path(info["purelib"]).resolve()
        if purelib not in installed.parents:
            return _fail("the probe imported %s from outside the install: %s"
                         % (PKG, installed))
        if (repo / PKG / "__init__.py").read_bytes() != installed.read_bytes():
            return _fail(
                "the installed %s is not byte-identical to the one in this "
                "checkout, so the probes above proved something about a stale "
                "artifact" % PKG)
        print("imported from: %s (byte-identical to this checkout)" % installed)

    print("verify_wheel: the installed wheel runs the API")
    return 0


if __name__ == "__main__":
    sys.exit(main())