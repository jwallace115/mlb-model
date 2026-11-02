#!/bin/bash
# RED-first behavioural test of P81 in a throwaway pair of repos: an add/add conflict on a soccer cache (Mac-owned → origin wins) and a
# content conflict on status/x.json (VM-owned → VM wins); a stale .git/rebase-merge/autostash must be cleared.
set -u
D=$(mktemp -d); cd "$D"
git init -q --bare origin.git
git clone -q origin.git mac && git clone -q origin.git vm
for r in mac vm; do git -C $r config user.email a@b; git -C $r config user.name t; done
cd "$D/mac"; mkdir -p soccer/data/cache/daily status; echo base > soccer/data/cache/daily/x.json; echo base > status/x.json; git add -A; git commit -qm base; git push -q origin HEAD:main
cd "$D/vm"; git pull -q origin main; git checkout -q -B main origin/main
cd "$D/mac"; echo mac > soccer/data/cache/daily/x.json; echo mac > status/x.json; git commit -qam mac; git push -q origin main
cd "$D/vm"; echo vm > soccer/data/cache/daily/x.json; echo vm > status/x.json; git commit -qam vm
mkdir -p .git/rebase-merge; echo deadbeef > .git/rebase-merge/autostash   # the stale dir
export REPO="$D/vm" LOG="$D/log.txt"
# run only the daemon's pull/resolve section by sourcing the functions and the pull block
DAEMON="$1"
bash -n "$DAEMON" || { echo "SYNTAX FAIL"; exit 1; }
# extract functions + stale-dir clearing + pull block into a runnable snippet
python3 - "$DAEMON" > "$D/snippet.sh" <<PY
import sys,re
s=open(sys.argv[1]).read()
a=s.index("# P81(a)"); b=s.index("# Stage all changes")
c=s.index("# Pull with rebase (P81"); d=s.index("fi\n", s.index("not resolvable by ownership rules"))+3
print('TIMESTAMP=t; LOG="'+"$LOG"+'"; cd "'+"$REPO"+'"'); print(s[a:b]); print(s[c:d])
PY
bash "$D/snippet.sh"; RC=$?
cd "$D/vm"; echo "rc=$RC soccer=$(cat soccer/data/cache/daily/x.json) status=$(cat status/x.json) rebase_dir=$([ -d .git/rebase-merge ] && echo present || echo gone)"
[ $RC -eq 0 ] && [ "$(cat soccer/data/cache/daily/x.json)" = mac ] && [ "$(cat status/x.json)" = vm ] && [ ! -d .git/rebase-merge ] && echo PASS || echo FAIL
