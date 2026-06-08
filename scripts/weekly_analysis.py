#!/usr/bin/env python3
"""
每周数据采集 + AI 分析 + Git 提交
由 Hermes cron job 调用（每周六 9:00）
"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
PYTHON = os.path.expanduser("~/AppData/Local/Programs/Python/Python311/python.exe")

# Step 1: Fetch latest data
print("=" * 40)
print("Step 1: Fetching latest fund data...")
r = subprocess.run([PYTHON, os.path.join(SCRIPT_DIR, "fetch_data.py")], cwd=PROJECT_DIR)
if r.returncode != 0:
    print("Data fetch FAILED. Aborting.", file=sys.stderr)
    sys.exit(1)

# Step 2: Generate AI analysis
print("=" * 40)
print("Step 2: Generating AI analysis...")
r = subprocess.run([PYTHON, os.path.join(SCRIPT_DIR, "generate_analysis.py")], cwd=PROJECT_DIR)
if r.returncode != 0:
    print("AI analysis FAILED", file=sys.stderr)
    # Continue anyway - at least push the data update

# Step 3: Commit & push
print("=" * 40)
print("Step 3: Pushing to GitHub...")
deploy_sh = os.path.join(SCRIPT_DIR, "deploy.sh")
r = subprocess.run(["bash", deploy_sh], cwd=SCRIPT_DIR)
if r.returncode != 0:
    print("Deploy FAILED", file=sys.stderr)

print("=" * 40)
print("Weekly analysis complete.")
