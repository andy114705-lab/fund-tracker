#!/usr/bin/env python3
"""
每日数据采集脚本
- AKShare 获取 A 股基金净值
- Finnhub 获取美股指数
- 输出 data/prices.json

用法: python fetch_data.py
"""

import json
import os
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
FUNDS_PATH = os.path.join(DATA_DIR, "funds.json")
PRICES_PATH = os.path.join(DATA_DIR, "prices.json")

# ============================================================
# A 股基金 — AKShare
# ============================================================
def fetch_a_fund_nav(fund_code: str) -> dict:
    """获取单只 A 股基金最新净值"""
    import akshare as ak
    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        if df is None or df.empty:
            return {"nav": None, "nav_date": None, "error": "无数据"}
        latest = df.iloc[-1]
        nav_val = float(latest.iloc[1]) if len(latest) > 1 else float(latest.iloc[0])
        return {
            "nav": round(nav_val, 4),
            "nav_date": str(latest.iloc[0])[:10],
            "error": None
        }
    except Exception as e:
        return {"nav": None, "nav_date": None, "error": str(e)[:200]}

def fetch_a_fund_history(fund_code: str, days: int = 30) -> list:
    """获取 A 股基金近期净值历史"""
    import akshare as ak
    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        if df is None or df.empty:
            return []
        records = []
        for _, row in df.tail(days).iterrows():
            records.append({
                "date": str(row.iloc[0])[:10],
                "nav": round(float(row.iloc[1]), 4)
            })
        return records
    except Exception:
        return []


# ============================================================
# 美股指数 — Finnhub
# ============================================================
def fetch_us_index(symbol: str, api_key: str) -> dict:
    """获取美股指数行情"""
    import finnhub
    client = finnhub.Client(api_key=api_key)
    try:
        quote = client.quote(symbol=symbol)
        return {
            "symbol": symbol,
            "price": round(quote["c"], 2),
            "change": round(quote["d"], 2),
            "change_pct": round(quote["dp"], 2),
            "high": round(quote["h"], 2),
            "low": round(quote["l"], 2),
            "error": None
        }
    except Exception as e:
        return {"symbol": symbol, "price": None, "error": str(e)[:200]}

def load_existing_prices():
    """加载已有价格数据"""
    if os.path.exists(PRICES_PATH):
        with open(PRICES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"updated": "", "funds": {}, "indices": {}}


def main():
    # 加载配置
    with open(FUNDS_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    prices = load_existing_prices()
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    # --- A 股基金 ---
    print("=" * 50)
    print("📊 采集 A 股基金净值...")
    a_funds = {k: v for k, v in config["funds"].items() if v["market"] == "A" and v["status"] != "watching"}
    for code in a_funds:
        name = config["funds"][code]["name"]
        result = fetch_a_fund_nav(code)
        if result["nav"] is not None:
            print(f"  ✅ {code} {name}: {result['nav']} ({result['nav_date']})")
            history = fetch_a_fund_history(code, days=60)
            if code not in prices["funds"]:
                prices["funds"][code] = {}
            prices["funds"][code]["nav"] = result["nav"]
            prices["funds"][code]["nav_date"] = result["nav_date"]
            prices["funds"][code]["history"] = history
        else:
            print(f"  ❌ {code} {name}: {result['error']}")

    # --- 美股指数 ---
    print("=" * 50)
    print("📊 采集美股指数...")
    finnhub_key = os.environ.get("FINNHUB_KEY", "")
    if not finnhub_key:
        # Fallback: read from Hermes .env
        import re as _re
        env_p = os.path.join(os.path.expanduser("~"), "AppData", "Local", "hermes", ".env")
        try:
            with open(env_p, "r") as _f:
                for _line in _f:
                    if "FINNHUB_KEY" in _line:
                        finnhub_key = _line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except (PermissionError, FileNotFoundError):
            pass
    if finnhub_key:
        us_indices = config.get("indices", {})
        for sym, info in us_indices.items():
            if info["market"] == "US":
                result = fetch_us_index(sym, finnhub_key)
                if result["price"] is not None:
                    print(f"  ✅ {sym} ({info['name']}): {result['price']} ({result['change_pct']}%)")
                    prices["indices"][sym] = result
                else:
                    print(f"  ❌ {sym} ({info['name']}): {result['error']}")
    else:
        print("  ⚠️ FINNHUB_KEY 未设置，跳过美股指数采集。")

    # --- A 股指数 — AKShare ---
    print("=" * 50)
    print("📊 采集 A 股指数...")
    a_indices = {k: v for k, v in config.get("indices", {}).items() if v["market"] == "A"}
    for sym, info in a_indices.items():
        try:
            import akshare as ak
            df = ak.stock_zh_index_daily(symbol=f"sh{sym}" if sym.startswith("0") else f"sz{sym}")
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                close = float(latest["close"])
                # 近似计算涨跌幅
                if len(df) >= 2:
                    prev = float(df.iloc[-2]["close"])
                    chg_pct = round((close - prev) / prev * 100, 2)
                else:
                    chg_pct = 0
                print(f"  ✅ {sym} ({info['name']}): {close} ({chg_pct}%)")
                prices["indices"][sym] = {
                    "symbol": sym,
                    "price": close,
                    "change_pct": chg_pct,
                    "error": None
                }
        except Exception as e:
            print(f"  ❌ {sym} ({info['name']}): {e}")

    # 写入
    prices["updated"] = today
    with open(PRICES_PATH, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)

    print("=" * 50)
    print(f"✅ 数据已写入 {PRICES_PATH}")
    print(f"   更新时间: {today}")


if __name__ == "__main__":
    main()
