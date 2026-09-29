#!/usr/bin/env bash
# ELOHIM installer.
#
# Thin wrapper: the real logic, including every guard, lives in
# tools/install.py so there is exactly one implementation.  This script only
# finds the repository root and hands over, which keeps the shell surface small
# enough to read at a glance.
#
# Usage:
#   ./install.sh                          # ~/.agents/skills/elohim
#   ./install.sh --skills-dir PATH        # any agent's own skills directory
#   ./install.sh --base .                 # project-local install
#   ./install.sh claude codex             # several standard layouts at once
#   ./install.sh --dry-run --force        # inspect, then replace without asking
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
runner="$here/tools/install.py"

if [ ! -f "$runner" ]; then
  printf 'install.sh: cannot find %s\n' "$runner" >&2
  printf 'install.sh: run this script from the repository root.\n' >&2
  exit 2
fi

if command -v python3 >/dev/null 2>&1; then
  py=python3
elif command -v python >/dev/null 2>&1; then
  py=python
else
  printf 'install.sh: no python3 or python on PATH; need Python 3.10 or newer.\n' >&2
  exit 2
fi

printf 'install.sh: repository  %s\n' "$here"
printf 'install.sh: interpreter %s (%s)\n' "$py" "$("$py" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
exec "$py" "$runner" "$@"
