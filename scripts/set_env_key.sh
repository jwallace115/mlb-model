#!/usr/bin/env bash
# Update one key in .env without it touching the terminal, shell history,
# the process table, or any chat transcript.
#
#   ./scripts/set_env_key.sh ODDS_API_KEY
#   ./scripts/set_env_key.sh CFBD_API_KEY
#
# Input is hidden (read -s), passed to python via the environment (not argv,
# so it never appears in `ps`), and unset immediately after.
set -euo pipefail

VAR="${1:-}"
if [[ -z "$VAR" ]]; then
  echo "usage: $0 <ENV_VAR_NAME>   e.g. $0 ODDS_API_KEY" >&2; exit 1
fi

cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo "no .env in $(pwd)" >&2; exit 1; }

if ! git check-ignore -q .env 2>/dev/null; then
  echo "REFUSING: .env is not gitignored. Fix that first." >&2; exit 1
fi

cp .env ".env.bak.$(date +%Y%m%d_%H%M%S)"

read -r -s -p "Paste value for ${VAR} (hidden, then Enter): " NEWVAL
echo

if [[ -z "$NEWVAL" ]]; then echo "empty value, aborting" >&2; exit 1; fi

VAR="$VAR" NEWVAL="$NEWVAL" python3 - <<'PYEOF'
import os, re, pathlib
var, val = os.environ["VAR"], os.environ["NEWVAL"].strip()
p = pathlib.Path(".env"); s = p.read_text()
line = f"{var}={val}"
if re.search(rf"^{re.escape(var)}=", s, flags=re.M):
    s = re.sub(rf"^{re.escape(var)}=.*$", line, s, count=1, flags=re.M)
    action = "replaced"
else:
    s = s.rstrip("\n") + "\n" + line + "\n"
    action = "appended"
p.write_text(s)
print(f"{var}: {action} ({len(val)} chars)")
PYEOF

unset NEWVAL
echo "Done. Value was never printed. Backup: .env.bak.*"
