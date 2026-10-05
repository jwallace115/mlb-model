#!/usr/bin/env bash
# OPS2: idempotent setup for picks ledger on the VM.
# Run: bash /root/mlb-model/site/ops/picks_ledger_setup.sh
set -euo pipefail

# Backup crontab first
crontab -l > "/root/crontab.bak.$(date -u +%Y%m%dT%H%MZ)"

# Directories
mkdir -p /root/private/ledger /root/private/ledger_backup /root/private/inbox_confirmed
chmod 700 /root/private

# members.json — ONLY if absent (Jeff adds handles by hand on the VM)
MEMBERS=/root/private/ledger/members.json
if [ ! -f "$MEMBERS" ]; then
    echo '{"members":["jeff"]}' > "$MEMBERS"
    echo "wrote $MEMBERS"
else
    echo "$MEMBERS already exists — not overwriting"
fi

# backup script
cat > /root/private/backup_picks.sh << 'BACKUP'
#!/usr/bin/env bash
set -euo pipefail
SRC=/root/private/ledger/picks.jsonl
DEST=/root/private/ledger_backup
if [ ! -f "$SRC" ]; then
    echo "no picks.jsonl yet — nothing to back up"
    exit 0
fi
TS=$(date -u +%Y%m%dT%H%M%SZ)
gzip -c "$SRC" > "$DEST/picks_${TS}.jsonl.gz"
# keep only the newest 30
cd "$DEST"
ls -1t picks_*.jsonl.gz | tail -n +31 | xargs -r rm --
echo "backed up picks.jsonl -> picks_${TS}.jsonl.gz ($(ls -1 picks_*.jsonl.gz | wc -l) kept)"
BACKUP
chmod +x /root/private/backup_picks.sh

# Cron lines — add only if absent
CRON=$(crontab -l 2>/dev/null || true)

LINE1="20 * * * * cd /root/mlb-model && PICKS_LEDGER_DIR=/root/private/ledger venv/bin/python3 shared/pipeline/picks_adapters.py >> /root/logs/picks_adapters.log 2>&1"
LINE2="35 5 * * * bash /root/private/backup_picks.sh >> /root/logs/picks_backup.log 2>&1"
LINE3="10 10 * * * cd /root/mlb-model && PICKS_LEDGER_DIR=/root/private/ledger venv/bin/python3 shared/pipeline/event_crosswalk.py && PICKS_LEDGER_DIR=/root/private/ledger venv/bin/python3 shared/pipeline/picks_grader.py >> /root/logs/picks_grader.log 2>&1"

CHANGED=0
if ! echo "$CRON" | grep -qF "picks_adapters.py"; then
    CRON="$CRON
$LINE1"
    CHANGED=1
    echo "added picks_adapters cron"
else
    echo "picks_adapters cron already present"
fi

if ! echo "$CRON" | grep -qF "backup_picks.sh"; then
    CRON="$CRON
$LINE2"
    CHANGED=1
    echo "added backup_picks cron"
else
    echo "backup_picks cron already present"
fi

if ! echo "$CRON" | grep -qF "picks_grader.py"; then
    CRON="$CRON
$LINE3"
    CHANGED=1
    echo "added picks_grader cron"
else
    echo "picks_grader cron already present"
fi

if [ "$CHANGED" -eq 1 ]; then
    echo "$CRON" | crontab -
    echo "crontab updated"
else
    echo "crontab unchanged"
fi

echo "done"
