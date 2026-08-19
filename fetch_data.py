from datetime import datetime
import json
import yfinance as yf


def analyze_and_generate():
    # 1. 抓取近 10 天布蘭特原油 (BZ=F) 與 匯率 (AUD/USD)
    oil = yf.Ticker("BZ=F").history(period="10d")["Close"]
    fx = yf.Ticker("AUDUSD=X").history(period="10d")["Close"]

    oil_now = round(oil.iloc[-1], 2)
    oil_7d_ago = oil.iloc[-7] if len(oil) >= 7 else oil.iloc[0]
    oil_change = round(((oil_now - oil_7d_ago) / oil_7d_ago) * 100, 2)

    fx_now = round(fx.iloc[-1], 4)
    fx_7d_ago = fx.iloc[-7] if len(fx) >= 7 else fx.iloc[0]
    fx_change = round(((fx_now - fx_7d_ago) / fx_7d_ago) * 100, 2)

    # 2. 自動綜合評價演算法
    # 當前假設本地油價處於週期低點 (TROUGH)
    cycle_text = "🟢 週期最低點 (Trough)"

    if oil_change > 3.0 or fx_change < -2.0:
        banner_color = "var(--accent-red)"
        status_text = f"🚨 暴漲預警發出！(原油 7 天大漲 {oil_change}%)"
        desc = "當前為地區價格最低點，但「國際原油大漲/本幣貶值」的成本壓力將在 3-5 天內全面傳導至零售端！加油站隨時會突發暴漲 35c+，建議立刻加滿。"
        score = 98
        retail_curve = [168, 168, 168, 210, 208, 205, 202, 199]
        scores_curve = [98, 90, 80, 20, 25, 30, 40, 50]
    elif oil_change < -3.0:
        banner_color = "var(--accent-blue)"
        status_text = f"📉 國際原油顯著下跌 (-{abs(oil_change)}%)"
        desc = "國際原油批發成本有所下降，零售端暴漲壓力減緩。目前價位相對平穩，可按需加油。"
        score = 75
        retail_curve = [168, 167, 166, 165, 165, 164, 200, 196]
        scores_curve = [75, 75, 70, 70, 65, 60, 25, 30]
    else:
        banner_color = "var(--accent-green)"
        status_text = "🟢 最佳加油窗口期 (低價區間)"
        desc = f"當前處於地區價格週期低點，且國際原油走勢平穩 (7天變動 {oil_change:+.1f}%)，屬於非常划算的加油時機。"
        score = 88
        retail_curve = [168, 168, 167, 167, 205, 202, 198, 195]
        scores_curve = [88, 85, 80, 75, 20, 30, 40, 50]

    # 計算原油傳導成本曲線
    oil_cost_curve = [
        round(oil_now + (i * (oil_change / 7.0)), 1) for i in range(8)
    ]

    # 3. 打包資料
    data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "evaluation": {
            "oil_status": desc,
            "score": score,
            "recommendation": status_text,
            "banner_color": banner_color,
        },
        "metrics": {
            "oil_price": oil_now,
            "oil_change": oil_change,
            "fx_change": fx_change,
            "cycle_text": cycle_text,
        },
        "chart_data": {
            "labels": [
                "Today",
                "Day 2",
                "Day 4",
                "Day 6",
                "Day 8",
                "Day 10",
                "Day 12",
                "Day 14",
            ],
            "retail_prices": retail_curve,
            "oil_costs": oil_cost_curve,
            "scores": scores_curve,
        },
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    analyze_and_generate()
