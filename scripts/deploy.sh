#!/bin/bash
# 数据提交推送脚本
# 由 cron job 调用，将更新后的数据提交到 GitHub

set -e
cd "$(dirname "$0")/.."

GIT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")

if [ -z "$GIT_REMOTE" ]; then
    echo "WARNING: No git remote set. Skipping push."
    echo "  Set up with: git remote add origin <your-github-repo-url>"
    exit 0
fi

# Add data files
git add data/funds.json data/investments.json data/prices.json data/analysis.json data/analysis.html web/

# Only commit if there are changes
if git diff --cached --quiet; then
    echo "No changes to commit."
    exit 0
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
git commit -m "auto: data update $TIMESTAMP"
git push origin main 2>&1 || git push origin master 2>&1

echo "Pushed to $GIT_REMOTE"
