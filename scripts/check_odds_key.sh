#!/usr/bin/env bash
# Which ODDS_API_KEY is actually in effect, and what quota does it carry?
# /sports is a FREE endpoint - it does not consume credits.
set -uo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
import hashlib, os, pathlib, re
def fp(v):
    v = (v or "").strip()
    return f"{hashlib.sha256(v.encode()).hexdigest()[:8]}  (len {len(v)})" if v else "<unset>"
m = re.search(r'^ODDS_API_KEY=(.*)$', pathlib.Path(".env").read_text(), re.M)
envfile = m.group(1) if m else ""
shell = os.environ.get("ODDS_API_KEY")
print(f"  .env      : {fp(envfile)}")
print(f"  shell env : {fp(shell)}")
if shell and shell.strip() != envfile.strip():
    print("\n  *** MISMATCH — a different key is exported in your shell.")
    print("      Before the override=True fix, THAT key was the one being used.")
    print("      Clear it with:  unset ODDS_API_KEY")
elif shell:
    print("\n  shell and .env agree")
else:
    print("\n  no shell override — .env is what runs")
PY

echo
echo "Live quota for the .env key (free endpoint, costs nothing):"
KEY=$(grep '^ODDS_API_KEY=' .env | cut -d= -f2- | tr -d '[:space:]')
curl -s -D - -o /dev/null "https://api.the-odds-api.com/v4/sports/?apiKey=${KEY}" \
  | grep -i "x-requests-\|HTTP/" | sed 's/^/  /'
