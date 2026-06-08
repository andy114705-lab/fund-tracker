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

# Copy data files into web/data/ for Cloudflare Pages
mkdir -p web/data
cp data/funds.json web/data/
cp data/investments.json web/data/
cp data/prices.json web/data/
cp data/analysis.json web/data/ 2>/dev/null || true
cp data/analysis.html web/data/ 2>/dev/null || true

# Add all files
git add data/ web/

# Only commit if there are changes
if git diff --cached --quiet; then
    echo "No changes to commit."
    exit 0
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
git commit -m "auto: data update $TIMESTAMP"
git push origin main 2>&1 || git push origin master 2>&1

echo "Pushed to $GIT_REMOTE"
