#!/usr/bin/env python3
"""
每日数据采集 + Git 提交
由 Hermes cron job 调用
"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.expanduser("~/AppData/Local/Programs/Python/Python311/python.exe")

# Step 1: Fetch data
print("=" * 40)
print("Step 1: Fetching fund data...")
r = subprocess.run([PYTHON, os.path.join(SCRIPT_DIR, "fetch_data.py")], cwd=SCRIPT_DIR)
if r.returncode != 0:
    print("Data fetch FAILED", file=sys.stderr)
    sys.exit(1)

# Step 2: Commit & push
print("=" * 40)
print("Step 2: Pushing to GitHub...")
deploy_sh = os.path.join(SCRIPT_DIR, "deploy.sh")
r = subprocess.run(["bash", deploy_sh], cwd=SCRIPT_DIR)
if r.returncode != 0:
    print("Deploy FAILED (maybe no git remote configured?)", file=sys.stderr)

print("=" * 40)
print("Daily update complete.")
