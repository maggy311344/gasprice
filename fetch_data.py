import base64
from datetime import datetime
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
import yfinance as yf


# 1. 抓取 TAS Hobart (Postcode 7000) 實時油價
def get_hobart_real_fuel_price():
    api_key = os.environ.get("FUELCHECK_API_KEY")
    api_secret = os.environ.get("FUELCHECK_API_SECRET")

    # 若未設定 API Key，則備用回傳 Tasmanian Hobart 歷史基準價
    if not api_key or not api_secret:
        print("未設定 FuelCheck API，使用 Hobart 預設基準價 172.9 c/L")
        return 172.9, "Hobart (預設)"

    try:
        # 取得 Access Token
        auth_str = f"{api_key}:{api_secret}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        headers_token = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        token_res = requests.get(
            "https://api.nsw.gov.au/oauth/client_credential/accesstoken?grant_type=client_credentials",
            headers=headers_token,
            timeout=10,
        )
        token = token_res.json().get("access_token")

        # 查詢 Hobart 7000 地區 Unleaded 91 (U91) 油價
        headers_api = {
            "Authorization": f"Bearer {token}",
            "apikey": api_key,
            "transactionid": "1",
            "requesttimestamp": datetime.now().strftime("%d/%m/%Y %I:%M:%S %p"),
            "Content-Type": "application/json",
        }

        # FuelCheck API endpoint for TAS prices
        url = "https://api.nsw.gov.au/FuelCheck/v1/fuel/prices/bypostcode?postcode=7000&fueltype=U91"
        res = requests.get(url, headers=headers_api, timeout=10)
        data = res.json()

        prices = [
            station["price"]
            for station in data.get("prices", [])
            if station.get("price")
        ]

        if prices:
            min_price = min(prices)
            print(
                f"✅ 成功抓取 Hobart 實時 U91 油價：最低 {min_price} c/L (共 {len(prices)} 間加油站)"
            )
            return min_price, "Hobart (實時)"
    except Exception as e:
        print(f"⚠️ 抓取 FuelCheck API 失敗：{e}，切換至備用估算數據")

    return 172.9, "Hobart (備用)"


# 2. 發送 Email 預警
def send_email_alert(subject, body_html):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    receiver_email = os.environ.get("RECEIVER_EMAIL")

    if not sender_email or not sender_password or not receiver_email:
        return

    receiver_list = [
        e.strip() for e in receiver_email.split(",") if e.strip()
    ]

    msg = MIMEMultipart()
    msg["From"] = f"油價預警機器人 <{sender_email}>"
    msg["To"] = ", ".join(receiver_list)
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg, to_addrs=receiver_list)
        server.quit()
        print(f"✅ 預警 Email 已寄出給 {len(receiver_list)} 位接收者！")
    except Exception as e:
        print(f"❌ 寄信失敗：{e}")


def analyze_and_generate():
    # A. 抓取金融市場數據
    oil = yf.Ticker("BZ=F").history(period="10d")["Close"]
    fx = yf.Ticker("AUDUSD=X").history(period="10d")["Close"]

    oil_now = round(oil.iloc[-1], 2)
    oil_7d_ago = oil.iloc[-7] if len(oil) >= 7 else oil.iloc[0]
    oil_change = round(((oil_now - oil_7d_ago) / oil_7d_ago) * 100, 2)

    fx_now = round(fx.iloc[-1], 4)
    fx_7d_ago = fx.iloc[-7] if len(fx) >= 7 else fx.iloc[0]
    fx_change = round(((fx_now - fx_7d_ago) / fx_7d_ago) * 100, 2)

    # B. 抓取 Hobart 當前實時油價
    hobart_price, source_label = get_hobart_real_fuel_price()

    should_send_email = False

    # C. 結合 Hobart 真實底價生成 14 天傳導預測
    base_price = hobart_price

    if oil_change > 3.0 or fx_change < -2.0:
        banner_color = "var(--accent-red)"
        status_text = f"🚨 暴漲預警！(Hobart 現價 {base_price}c / 原油 7 天漲 {oil_change}%)"
        desc = f"Hobart 當前最低 U91 現價為 <strong>{base_price} c/L</strong>。因國際原油/匯率成本壓力增加，預計 3-5 天內 Hobart 零售端將出現顯著調漲，建議抽空加滿。"
        score = 98
        retail_curve = [
            base_price,
            base_price,
            base_price + 2,
            base_price + 35,
            base_price + 33,
            base_price + 30,
            base_price + 28,
            base_price + 25,
        ]
        scores_curve = [98, 90, 80, 20, 25, 30, 40, 50]
        should_send_email = True
    elif oil_change < -3.0:
        banner_color = "var(--accent-blue)"
        status_text = (
            f"📉 原油下跌 (Hobart 現價 {base_price}c / 原油跌 {abs(oil_change)}%)"
        )
        desc = f"Hobart 當前最低 U91 現價為 <strong>{base_price} c/L</strong>。國際原油成本回落，零售價短時間內暴漲風險低，可按需加油。"
        score = 75
        retail_curve = [
            base_price,
            base_price - 1,
            base_price - 2,
            base_price - 3,
            base_price - 3,
            base_price - 4,
            base_price - 4,
            base_price - 5,
        ]
        scores_curve = [75, 75, 70, 70, 65, 60, 55, 50]
    else:
        banner_color = "var(--accent-green)"
        status_text = f"🟢 走勢平穩 (Hobart 實時最低價 {base_price} c/L)"
        desc = f"Hobart 當前最低 U91 現價為 <strong>{base_price} c/L</strong>。國際原油走勢平穩 (7天變動 {oil_change:+.1f}%)，價格波動溫和。"
        score = 88
        retail_curve = [
            base_price,
            base_price,
            base_price + 1,
            base_price + 1,
            base_price + 2,
            base_price + 2,
            base_price + 3,
            base_price + 3,
        ]
        scores_curve = [88, 85, 80, 75, 70, 65, 60, 55]

    oil_cost_curve = [
        round(oil_now + (i * (oil_change / 7.0)), 1) for i in range(8)
    ]

    # D. 發送 Email
    if should_send_email:
        email_subject = f"⛽【Hobart 油價預警】原油大漲 {oil_change}%！Hobart 當前最低價 {base_price}c/L"
        email_body = f"""
        <h2>🚨 Hobart 油價即將調漲預警</h2>
        <p>系統檢測到市場行情與 Hobart 實時數據：</p>
        <ul>
            <li><strong>Hobart U91 當前最低現價：</strong> <span style="color:blue; font-weight:bold;">{base_price} c/L</span></li>
            <li><strong>布蘭特原油現價：</strong> ${oil_now} USD</li>
            <li><strong>近 7 天原油漲幅：</strong> <span style="color:red; font-weight:bold;">+{oil_change}%</span></li>
        </ul>
        <hr>
        <p><strong>💡 建議行動：</strong> 原油進口成本壓力將於近日傳導至塔斯馬尼亞零售端，建議於 1-2 天內加滿。</p>
        <p><a href="https://maggy311344.github.io/gasprice/">👉 點此開啟 Hobart 油價儀表板</a></p>
        """
        send_email_alert(email_subject, email_body)

    # E. 寫入 data.json
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
            "cycle_text": f"📍 {source_label} 最低價 {base_price}c",
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
            "retail_prices": [round(p, 1) for p in retail_curve],
            "oil_costs": oil_cost_curve,
            "scores": scores_curve,
        },
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    analyze_and_generate()
