#!/usr/bin/env python3
"""Site enumeration for the A2 mutation census.

`mutate.py` gave every operator the same shape: walk the tree, take the FIRST
node matching a predicate, mutate it, return True. That makes every repeat of
an (operator, skill) pair land on the same site. The N=200 run sampled 47 of 48
(operator, skill) cells but only ever hit site #1 in each one, and its 10
"effective survivors" turned out to be 2 distinct mutants sampled 4 and 6 times.

So the census is split here into two halves:

  targets(tree)   every node this operator is willing to touch, in the same
                  deterministic order the old single-site loop used.
  mutate_one(node) the edit itself.

Sampling without replacement over (operator x skill x site) is then the only
way N means what it claims. The population is finite and enumerable, so the
first thing to measure is its size -- if it is smaller than N, the honest
census is the whole population, not N draws from it.
"""
from __future__ import annotations

import ast
from typing import Callable, TypedDict

# ------------------------------------------------------------------ predicates

def _is_num(node: ast.AST) -> bool:
    return (isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool))


def _is_tolerance(node: ast.AST) -> bool:
    # Spelled out rather than `_is_num(node) and 0 < abs(node.value) < 1`:
    # the predicate cannot see through the isinstance() inside _is_num, so the
    # short-circuit form leaves mypy reading .value off a bare ast.AST.
    if not (isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)):
        return False
    return 0 < abs(node.value) < 1


def _is_bool(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _is_literal_expr(node: ast.AST) -> bool:
    try:
        ast.literal_eval(node)
        return True
    except Exception:
        return False


def _docstring_body(node: ast.AST) -> bool:
    """A node whose first statement is a string literal, and which has more."""
    body = getattr(node, "body", None)
    if not body or len(body) < 2:
        return False
    first = body[0]
    return (isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str))


# -------------------------------------------------------------------- targets

def t_num(tree):    return [n for n in ast.walk(tree) if _is_num(n)]
def t_cmp(tree):    return [n for n in ast.walk(tree)
                          if isinstance(n, ast.Compare) and n.ops]
def t_bool(tree):   return [n for n in ast.walk(tree) if _is_bool(n)]
def t_tol(tree):    return [n for n in ast.walk(tree) if _is_tolerance(n)]
def t_ret(tree):    return [n for n in ast.walk(tree)
                          if isinstance(n, ast.Return) and n.value is not None
                          and _is_literal_expr(n.value)]
def t_doc(tree):    return [n for n in ast.walk(tree)
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                             ast.ClassDef, ast.Module))
                          and _docstring_body(n)]

# ------------------------------------------------------------------- mutators

def m_num_mul(node):
    value = float(node.value)
    node.value = 1e-9 if value == 0 else (value * (1.0 + 1e-3) if abs(value) > 1e-6
                                          else value + 1e-6)


def m_num_add(node):
    node.value = float(node.value) + 1.0


_CMP_FLIP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt,
             ast.Gt: ast.GtE, ast.GtE: ast.Gt,
             ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}


def m_cmp_flip(node):
    node.ops = [_CMP_FLIP[type(op)]() if type(op) in _CMP_FLIP else op
                for op in node.ops]


def m_bool_flip(node):
    node.value = not node.value


def m_tol_widen(node):
    node.value = node.value * 1000.0


def m_ret_flip(node):
    value = ast.literal_eval(node.value)
    node.value = ast.Constant(value=(not value) if isinstance(value, bool) else 0)


def m_ret_type(node):
    value = ast.literal_eval(node.value)
    node.value = ast.Constant(value=0 if isinstance(value, bool) else True)


def m_doc_kill(node):
    node.body.pop(0)


class Operator(TypedDict):
    """The declared shape of one operator row.

    OPERATORS is data, so its values are heterogeneous by construction and
    mypy infers every lookup as `object` without this. That is not cosmetic:
    an untyped `op["targets"](tree)` is a call on something mypy has proved
    it knows nothing about, which is exactly how a table entry gets a typo
    and ships.
    """

    name: str
    targets: Callable[[ast.AST], list[ast.AST]]
    mutate: Callable[[ast.AST], None]
    expect: str


OPERATORS: list[Operator] = [
    {"name": "num_mul", "targets": t_num, "mutate": m_num_mul,
     "expect": "value moves off its recorded result"},
    {"name": "num_add", "targets": t_num, "mutate": m_num_add,
     "expect": "numeric literal shifted by 1.0"},
    {"name": "cmp_flip", "targets": t_cmp, "mutate": m_cmp_flip,
     "expect": "comparison boundary moved"},
    {"name": "bool_flip", "targets": t_bool, "mutate": m_bool_flip,
     "expect": "boolean guard inverted"},
    {"name": "tol_widen", "targets": t_tol, "mutate": m_tol_widen,
     "expect": "tolerance widened 1000x"},
    {"name": "ret_flip", "targets": t_ret, "mutate": m_ret_flip,
     "expect": "return value negated in place"},
    {"name": "ret_type", "targets": t_ret, "mutate": m_ret_type,
     "expect": "return's TYPE changed; found the reproducibility:307 survivor"},
    {"name": "docstring_kill", "targets": t_doc, "mutate": m_doc_kill,
     "expect": "docstring removed; a MUTANT PROOF run of this class should be inert"},
]

INERT_OPERATORS = {"docstring_kill"}
BY_NAME = {op["name"]: op for op in OPERATORS}


def enumerate_sites(source: str) -> dict[str, list[dict]]:
    """Every (operator, site) pair in one instrument, with the site pinned by
    its line number in the PRISTINE source, which ast.unparse does not shift."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    lines = source.splitlines()
    out: dict[str, list[dict]] = {}
    for op in OPERATORS:
        rows = []
        for index, node in enumerate(op["targets"](tree)):
            # ast.Module carries no lineno, so the module docstring -- which
            # docstring_kill is declared to target -- would be recorded at line
            # 0 with no source text, and a row that cannot be located cannot be
            # checked against the tree. A module's docstring is always its
            # first line, so that is where the position is read from.
            lineno = getattr(node, "lineno", None) or 1
            text = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
            rows.append({"index": index, "lineno": lineno,
                         "col": getattr(node, "col_offset", 0),
                         "site": text[:120]})
        if rows:
            out[op["name"]] = rows
    return out


def apply_at(source: str, operator: str, index: int) -> str | None:
    """Mutate exactly site `index` of `operator`. None if absent or unloadable."""
    op = BY_NAME[operator]
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    nodes = op["targets"](tree)
    if not 0 <= index < len(nodes):
        return None
    op["mutate"](nodes[index])
    try:
        text = ast.unparse(tree)
        compile(text, "<mutant>", "exec")
    except Exception:
        # A mutant the interpreter cannot load never reaches the gate's
        # reasoning, so it cannot be evidence either way.
        return None
    return text