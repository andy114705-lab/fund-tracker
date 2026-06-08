#!/usr/bin/env python3
"""
每周 AI 分析报告生成脚本
用法: python generate_analysis.py
"""

import json
import os
import re
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")


def get_api_key():
    """获取 DeepSeek API Key"""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key and len(key) > 5:
        return key

    env_path = os.path.join(
        os.path.expanduser("~"), "AppData", "Local", "hermes", ".env"
    )
    try:
        with open(env_path, "r") as f:
            for line in f:
                if "DEEPSEEK_API_KEY" not in line:
                    continue
                # Extract value after '='
                eq_pos = line.index("=")
                val = line[eq_pos + 1:].strip()
                val = val.strip('"').strip("'").strip()
                if len(val) > 5:
                    return val
                break
    except (PermissionError, ValueError):
        pass
    return None


api_key = get_api_key()
if not api_key:
    print("ERROR: DEEPSEEK_API_KEY not found")
    sys.exit(1)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_context():
    funds = load_json(os.path.join(DATA_DIR, "funds.json"))
    investments = load_json(os.path.join(DATA_DIR, "investments.json"))
    prices = load_json(os.path.join(DATA_DIR, "prices.json"))

    fund_invested = {}
    for r in investments["records"]:
        fund_invested[r["code"]] = fund_invested.get(r["code"], 0) + r["amount"]

    fund_details = []
    for code, f in funds["funds"].items():
        invested = fund_invested.get(code, 0)
        nav = None
        nav_date = None
        if code in prices.get("funds", {}):
            nav = prices["funds"][code].get("nav")
            nav_date = prices["funds"][code].get("nav_date")

        ret_pct = None
        if nav and invested > 0 and code in prices.get("funds", {}):
            hist = prices["funds"][code].get("history", [])
            if hist and len(hist) > 1:
                avg = sum(h["nav"] for h in hist) / len(hist)
                if avg > 0:
                    units = invested / avg
                    value = units * nav
                    ret_pct = round((value - invested) / invested * 100, 2)

        fund_details.append({
            "code": code, "name": f["name"], "category": f["category"],
            "market": f["market"], "status": f["status"],
            "start_date": f.get("start_date", ""),
            "weekly_amount": f.get("weekly_amount", 0),
            "invested": invested, "nav": nav, "nav_date": nav_date,
            "est_return_pct": ret_pct,
            "pause_reason": f.get("pause_reason", ""),
        })

    index_data = {}
    for sym, info in funds.get("indices", {}).items():
        if sym in prices.get("indices", {}):
            d = prices["indices"][sym]
            index_data[sym] = {
                "name": info["name"],
                "price": d.get("price"),
                "change_pct": d.get("change_pct"),
            }

    return {
        "as_of": prices.get("updated", ""),
        "funds": fund_details,
        "indices": index_data,
        "total_invested": sum(f["invested"] for f in fund_details),
    }


def call_deepseek(prompt):
    import urllib.request
    import urllib.error

    data = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")[:500]
        raise RuntimeError(f"API error [{e.code}]: {body}")


SYSTEM_PROMPT = """你是一位拥有 20 年以上实战经验的投资专家和基金经理。
分析风格：基于数据、深刻洞察、说人话、敢给明确建议、指出问题不拐弯。
输出语言：中文。"""


def build_prompt(ctx):
    lines = [
        "以下是用户基金定投组合的真实数据。请给出专业投资分析和建议。",
        f"数据截至：{ctx['as_of']}",
        f"总投入：{ctx['total_invested']} 元",
        "",
        "=== 持仓基金 ===",
    ]
    for f in ctx["funds"]:
        s = {"active": "定投中", "paused": "暂停", "watching": "观察中"}.get(
            f["status"], f["status"]
        )
        lines.append(f"\n{f['code']} {f['name']}")
        lines.append(
            f"  类型:{f['category']} | 市场:{f['market']} | 状态:{s}"
        )
        lines.append(
            f"  开始:{f['start_date'] or '未开始'} | "
            f"周投:{f['weekly_amount']}元 | 累计投入:{f['invested']}元"
        )
        lines.append(f"  最新净值:{f['nav'] or '无'} ({f['nav_date'] or ''})")
        if f["est_return_pct"] is not None:
            sign = "+" if f["est_return_pct"] >= 0 else ""
            lines.append(f"  估算收益率:{sign}{f['est_return_pct']}%")
        if f["pause_reason"]:
            lines.append(f"  暂停原因:{f['pause_reason']}")

    if ctx["indices"]:
        lines.append("\n=== 市场指数 ===")
        for s, d in ctx["indices"].items():
            sign = "+" if (d.get("change_pct") or 0) >= 0 else ""
            lines.append(
                f"  {s}({d['name']}): {d.get('price','N/A')} "
                f"涨跌:{sign}{d.get('change_pct','N/A')}%"
            )

    lines.append("""

=== 分析要求 ===
按以下结构用 Markdown 输出：

## 市场概况
- 中美市场宏观环境（3-5句）
- 本周影响持仓的关键事件/趋势

## 组合诊断
- 整体评价
- 最大风险（仓位集中、行业相关性、QDII额度等）
- 进攻型 vs 防御型仓位比例分析

## 单只基金分析
逐只分析「定投中」的基金：估值水平、行业趋势、一句话判断

## 定投调整建议（信号矩阵）
| 基金 | 信号 | 理由 |
信号: 🟢维持 🟡减半 🔴暂停 ⬆️加码

对暂停的基金给出恢复建议。对观察中的基金给出开仓建议。

## 风险提示
未来1-2周关注的风险事件，组合层面风险敞口提醒。

---
注意：基于真实净值数据，缺少关键数据时明确说明，建议要具体可执行。
""")

    return "\n".join(lines)


def md_to_html(md):
    """Simple markdown to HTML converter"""
    import re as _re
    if not md:
        return ""
    lines = md.split("\n")
    result = []
    in_table = False
    in_list = False
    table_rows = []

    def close_table():
        nonlocal in_table, table_rows
        if in_table:
            result.append("<table><tbody>" + "".join(table_rows) + "</tbody></table>")
            table_rows = []
            in_table = False

    def close_list():
        nonlocal in_list
        if in_list:
            result.append("</ul>")
            in_list = False

    def inline(text):
        text = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = _re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
        text = _re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        return text

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            close_table()
            close_list()
            i += 1
            continue

        # HR
        if _re.match(r"^[-*_]{3,}$", line):
            close_table(); close_list()
            result.append("<hr>")
            i += 1
            continue

        # Headings
        hm = _re.match(r"^(#{1,6})\s+(.+)$", line)
        if hm:
            close_table(); close_list()
            lvl = len(hm.group(1))
            result.append(f"<h{lvl}>{inline(hm.group(2))}</h{lvl}>")
            i += 1
            continue

        # Table
        if line.startswith("|") and line.endswith("|"):
            close_list()
            if _re.match(r"^\|[\s\-:]+\|", line):
                i += 1
                continue
            if not in_table:
                in_table = True
            cells = [inline(c.strip()) for c in line.split("|")[1:-1]]
            tag = "th" if len(table_rows) == 0 else "td"
            row = "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"
            table_rows.append(row)
            i += 1
            continue
        else:
            close_table()

        # Unordered list
        if _re.match(r"^[-*+]\s+", line):
            close_table()
            if not in_list:
                result.append("<ul>")
                in_list = True
            cleaned = _re.sub(r"^[-*+]\s+", "", line)
            result.append(f"<li>{inline(cleaned)}</li>")
            i += 1
            continue

        # Regular text
        close_list()
        result.append(f"<p>{inline(line)}</p>")
        i += 1

    close_table()
    close_list()
    return "\n".join(result)


def main():
    ctx = build_context()
    prompt = build_prompt(ctx)

    print(f"Generating analysis...")
    print(f"  Data as of: {ctx['as_of']}")
    print(f"  Total invested: {ctx['total_invested']}")
    print()

    try:
        analysis = call_deepseek(prompt)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Save JSON first (raw markdown)

    json_path = os.path.join(DATA_DIR, "analysis.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "data_as_of": ctx["as_of"],
                "content": analysis,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    html_path = os.path.join(DATA_DIR, "analysis.html")
    now_str = datetime.now().strftime("%Y-%m-%d")

    # Convert markdown to HTML for standalone viewing
    analysis_html = md_to_html(analysis)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>投资分析报告 - {now_str}</title>
<style>
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
background:#0f1117;color:#e1e4ed;padding:20px;max-width:900px;margin:0 auto;line-height:1.8}}
h2{{color:#3b82f6;border-bottom:1px solid #2a2d3e;padding-bottom:8px;margin-top:28px}}
h3{{color:#e1e4ed;margin-top:24px;font-size:1.1em}}
h4{{color:#8b90a5;margin-top:20px}}
table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:0.92em}}
th{{background:#1a1d2e;color:#8b90a5;padding:10px 14px;text-align:left;font-weight:500}}
td{{padding:10px 14px;border-bottom:1px solid #2a2d3e}}
tr:hover{{background:#1a1d2e}}
hr{{border:none;border-top:1px solid #2a2d3e;margin:24px 0}}
ul,ol{{padding-left:24px;margin:12px 0}}
li{{margin:4px 0}}
strong{{color:#e1e4ed}}
code{{background:#1a1d2e;padding:2px 6px;border-radius:4px;font-size:0.9em}}
.meta{{color:#8b90a5;font-size:0.85em;margin-bottom:24px}}
.green{{color:#22c55e}}
.red{{color:#ef4444}}
</style></head>
<body>
<h2>📊 基金定投分析报告</h2>
<p class="meta">生成: {datetime.now().strftime("%Y-%m-%d %H:%M")} | 数据: {ctx["as_of"]}</p>
{analysis_html}
</body></html>"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"DONE: {json_path}")
    print(f"DONE: {html_path}")
    print(f"Content length: {len(analysis)} chars")


if __name__ == "__main__":
    main()
