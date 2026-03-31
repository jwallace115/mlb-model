#!/bin/bash
# iamnotuncertain deploy script
# Usage: ./deploy.sh "commit message"

set -e

MSG=${1:-"update"}

echo "=== Pushing to GitHub ==="
git add -A
git commit -m "$MSG" || echo "Nothing to commit"
git pull --rebase origin main
git push

echo "=== Syncing VM ==="
ssh root@142.93.242.4 "cd /root/mlb-model && git pull"

echo "=== Deploy complete ==="
