import json
import numpy as np
import yfinance as yf


def get_market_data():
    # 1. 抓取原油與匯率 (以 AUD/USD 為例)
    oil = yf.Ticker("CL=F").history(period="10d")["Close"]
    fx = yf.Ticker("AUDUSD=X").history(period="10d")["Close"]

    oil_change = (oil.iloc[-1] - oil.iloc[-7]) / oil.iloc[-7] * 100
    fx_change = (fx.iloc[-1] - fx.iloc[-7]) / fx.iloc[-7] * 100

    # 2. 自動評價邏輯
    if oil_change > 3:
        oil_eval = "UP_LARGE"
        oil_desc = f"國際原油近 7 天大漲 {oil_change:.1f}%"
    elif oil_change < -3:
        oil_eval = "DOWN_LARGE"
        oil_desc = f"國際原油近 7 天大跌 {abs(oil_change):.1f}%"
    else:
        oil_eval = "FLAT"
        oil_desc = "國際原油處於持平震盪階段"

    # 3. 模擬本地週期判斷與 14 天預測數據 (實際可介接當地油價 API)
    # 這裡會依據演算結果自動產出數據，供前端直接繪製圖表
    output_data = {
        "last_updated": "今天",
        "evaluation": {
            "oil_status": oil_desc,
            "score": 88 if oil_eval == "FLAT" else 95,
            "recommendation": "🟢 最佳加油窗口期：原油走勢平穩，本地價位處於低點！",
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
            "retail_prices": [168, 168, 168, 205, 202, 198, 195, 192],
            "oil_costs": [
                round(oil.iloc[-1], 1),
                round(oil.iloc[-1] * 1.01, 1),
                round(oil.iloc[-1] * 1.02, 1),
            ]
            * 3,
            "scores": [90, 85, 80, 20, 30, 40, 50, 60],
        },
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    get_market_data()
