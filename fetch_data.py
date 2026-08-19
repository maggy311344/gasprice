from datetime import datetime
import json
import yfinance as yf


def analyze_and_generate():
    # 1. 抓取近 10 天布蘭特原油 (BZ=F) 與 匯率 (AUD/USD 或 TWD/USD)
    oil = yf.Ticker("BZ=F").history(period="10d")["Close"]
    fx = yf.Ticker("AUDUSD=X").history(period="10d")["Close"]

    # 2. 自動計算原油 7 天變動率 %
    oil_now = oil.iloc[-1]
    oil_7d_ago = oil.iloc[-7] if len(oil) >= 7 else oil.iloc[0]
    oil_change = ((oil_now - oil_7d_ago) / oil_7d_ago) * 100

    # 3. 系統自動邏輯評價
    if oil_change > 3.0:
        status_text = f"🚨 國際原油大漲 (+{oil_change:.1f}%)，零售端即將面臨大幅漲價壓力！"
        score = 95
        recommend = "🟢 強烈建議今天加滿！(暴漲預警)"
    elif oil_change < -3.0:
        status_text = f"📉 國際原油大幅下跌 (-{abs(oil_change):.1f}%)，市場批發成本下降。"
        score = 50
        recommend = "🔵 觀望按需加油 (油價有下跌空間)"
    else:
        status_text = f"⚖️ 國際原油呈持平震盪走勢 (變動 {oil_change:+.1f}%)，走勢平穩。"
        score = 85
        recommend = "🟢 最佳加油窗口期：原油走勢平穩，可安心加油。"

    # 4. 打包數據輸出給網頁
    data = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "evaluation": {
            "oil_status": status_text,
            "score": score,
            "recommendation": recommend,
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
            "retail_prices": [168, 168, 167, 205, 202, 198, 195, 192],
            "oil_costs": [round(oil_now, 1)] * 8,
            "scores": [
                score,
                score - 5,
                score - 10,
                20,
                30,
                40,
                50,
                60,
            ],
        },
    }

    # 寫入成 data.json 供前端網頁讀取
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    analyze_and_generate()
