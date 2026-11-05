#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
PY="$PWD/.venv/bin/python"
status=0
for dir in lab1 lab2 lab3 lab4 lab5 lab6 lab7 .; do
  [ -e "$dir" ] || continue
  if [ "$dir" = "." ]; then [ -d tests ] || continue; target=tests; else target=.; fi
  ls "$dir"/test_*.py >/dev/null 2>&1 || [ "$dir" = "." ] || continue
  printf '%-6s ' "$dir"
  (cd "$dir" && "$PY" -m pytest "$target" -q 2>&1 | tail -1) || status=1
done
exit $status
