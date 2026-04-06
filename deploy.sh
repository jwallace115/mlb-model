#!/bin/bash
# iamnotuncertain deploy script
# Usage: ./deploy.sh "commit message"

set -e

MSG=${1:-"update"}

# Pre-deploy validation
echo "Running pre-deploy validation..."
python3 shared/pre_deploy_check.py
if [ $? -ne 0 ]; then
    echo "❌ Pre-deploy validation FAILED. Fix errors before deploying."
    exit 1
fi
echo "✅ Validation passed. Deploying..."

echo "=== Pushing to GitHub ==="
git add -A
git commit -m "$MSG" || echo "Nothing to commit"
git pull --rebase origin main
git push

echo "=== Syncing VM ==="
ssh root@142.93.242.4 "cd /root/mlb-model && git pull"

echo "=== Deploy complete ==="
