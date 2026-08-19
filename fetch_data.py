import base64
from datetime import datetime
import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo
import requests
import yfinance as yf


# 1. 抓取 Lutana / Hobart (Postcode 7009 & 7000) 實時油價（帶完整排錯日誌）
def get_hobart_real_fuel_price():
    api_key = os.environ.get("FUELCHECK_API_KEY")
    api_secret = os.environ.get("FUELCHECK_API_SECRET")

    # 檢查 1：是否缺乏 API 金鑰設定
    if not api_key or not api_secret:
        print("❌ [Error] 未設定 FUELCHECK_API_KEY 或 FUELCHECK_API_SECRET 秘鑰！")
        return None, "⚠️ 秘鑰未設定", "請在 GitHub Secrets 設定 API 金鑰"

# Step A: 取得 OAuth Token (使用正確的 api.onegov.nsw.gov.au 域名)
    token = None
    try:
        auth_str = f"{api_key}:{api_secret}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        headers_token = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        token_url = "https://api.onegov.nsw.gov.au/oauth/client_credential/accesstoken?grant_type=client_credentials"
        token_res = requests.get(token_url, headers=headers_token, timeout=10)

        if token_res.status_code != 200:
            print(
                f"❌ [OAuth Failed] HTTP {token_res.status_code} | 回傳內容:"
                f" {token_res.text}"
            )
            return (
                None,
                f"⚠️ Token 驗證失敗 (HTTP {token_res.status_code})",
                token_res.text,
            )

        token = token_res.json().get("access_token")
        print("✅ OAuth Token 取得成功！")
    except Exception as e:
        print(f"❌ [OAuth Exception] 連線異常: {str(e)}")
        return None, "⚠️ OAuth 連線異常", str(e)
    
# Step B: 使用 v2 API (POST 方式) 查詢 7009 與 7000 地區
    postcodes = ["7009", "7000"]
    combined_results = []

    # 採用官方要求的 UTC 時間格式
    utc_timestamp = datetime.utcnow().strftime("%d/%m/%Y %I:%M:%S %p")

    headers_api = {
        "Authorization": f"Bearer {token}",
        "apikey": api_key,
        "transactionid": "1",
        "requesttimestamp": utc_timestamp,
        "Content-Type": "application/json; charset=utf-8",
    }

    url = "https://api.onegov.nsw.gov.au/FuelCheck/v2/fuel/prices/bypostcode?states=TAS"

    for pc in postcodes:
        payload = {
            "fueltype": "U91",
            "namedlocation": pc,
            "sortby": "Price",
            "sortascending": "true",
        }
        try:
            res = requests.post(
                url, headers=headers_api, json=payload, timeout=10
            )

            if res.status_code == 200:
                data = res.json()
                # 建立站點對照表
                stations = {
                    str(s.get("code")): s for s in data.get("stations", [])
                }
                prices = data.get("prices", [])

                # 組合價格與站點資料
                for p in prices:
                    st_code = str(p.get("stationcode"))
                    st_info = stations.get(st_code, {})
                    combined_results.append(
                        {
                            "price": p.get("price"),
                            "stationname": st_info.get(
                                "name", "Hobart 加油站"
                            ),
                            "address": st_info.get("address", f"Postcode {pc}"),
                        }
                    )
                print(
                    f"ℹ️ Postcode {pc} (v2) 成功取得 {len(prices)} 筆 U91 油價"
                )
            else:
                print(
                    f"⚠️ [API Warning] Postcode {pc} HTTP {res.status_code}:"
                    f" {res.text}"
                )
        except Exception as e:
            print(f"⚠️ [API Exception] Postcode {pc} 連線異常: {str(e)}")

    if not combined_results:
        print("❌ [Data Error] v2 API 未回傳 7009/7000 地區的有效數據！")
        return (
            None,
            "⚠️ 無油價資料",
            "API 未回傳 7009/7000 地區的有效加油站數據",
        )

    # Step C: 優先匹配 Lutana / Brooker Hwy 站點，否則取區域最低價
    lutana_stations = [
        s
        for s in combined_results
        if "brooker" in s.get("address", "").lower()
        or "lutana" in s.get("address", "").lower()
        or "lutana" in s.get("stationname", "").lower()
    ]

    target_list = lutana_stations if lutana_stations else combined_results
    cheapest = min(
        target_list, key=lambda x: x.get("price", 999) if x.get("price") else 999
    )

    price = cheapest.get("price")
    station_name = cheapest.get("stationname", "Hobart 加油站")
    address = cheapest.get("address", "Lutana / Hobart")

    print(
        f"🎯 [Success] 成功鎖定實時站點: {station_name} ({address}) - 價格:"
        f" {price} c/L"
    )
    return price, station_name, address


# 2. Email 預警發送
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
        print("✅ 預警 Email 已寄出！")
    except Exception as e:
        print(f"❌ 寄信失敗：{e}")


def analyze_and_generate():
    # 時區設定：Hobart 當地時間
    hobart_tz = ZoneInfo("Australia/Hobart")
    now_hobart = datetime.now(hobart_tz)
    time_str = now_hobart.strftime("%Y-%m-%d %H:%M:%S (Hobart Time)")

    # A. 金融數據抓取
    oil = yf.Ticker("BZ=F").history(period="10d")["Close"]
    fx = yf.Ticker("AUDUSD=X").history(period="10d")["Close"]

    oil_now = round(oil.iloc[-1], 2)
    oil_7d_ago = oil.iloc[-7] if len(oil) >= 7 else oil.iloc[0]
    oil_change = round(((oil_now - oil_7d_ago) / oil_7d_ago) * 100, 2)

    fx_now = round(fx.iloc[-1], 4)
    fx_7d_ago = fx.iloc[-7] if len(fx) >= 7 else fx.iloc[0]
    fx_change = round(((fx_now - fx_7d_ago) / fx_7d_ago) * 100, 2)

    # B. 抓取實時油價
    hobart_price, station_name, station_address = get_hobart_real_fuel_price()

    # 若抓取失敗的處理邏輯 (不隱瞞錯誤)
    if hobart_price is None:
        base_price = 200.0  # 圖表顯示用的基準占位值
        price_display = "⚠️ API 擷取失敗"
        cycle_text = f"📍 {station_name}"
        desc = f"<strong>資料擷取提醒：</strong>無法取得 Hobart/Lutana 實時油價數據。原因：<code>{station_address}</code>。請至 GitHub Actions 檢視詳細 Log。"
        banner_color = "var(--accent-red)"
        status_text = "⚠️ 油價數據擷取異常"
        score = 0
        retail_curve = [200] * 8
        scores_curve = [0] * 8
    else:
        base_price = hobart_price
        price_display = f"{base_price} c/L"
        cycle_text = f"📍 {station_name} ({base_price}c)"

        if oil_change > 3.0 or fx_change < -2.0:
            banner_color = "var(--accent-red)"
            status_text = f"🚨 暴漲預警！({station_name} {base_price}c / 原油漲 {oil_change}%)"
            desc = f"<strong>{station_name}</strong>（{station_address}）目前 U91 現價為 <strong>{base_price} c/L</strong>。因國際成本調漲，預計 3-5 天內將有顯著漲幅，建議盡快加滿。"
            score = 98
            retail_curve = [
                base_price,
                base_price,
                base_price + 2,
                base_price + 25,
                base_price + 23,
                base_price + 20,
                base_price + 18,
                base_price + 15,
            ]
            scores_curve = [98, 90, 80, 20, 25, 30, 40, 50]
        elif oil_change < -3.0:
            banner_color = "var(--accent-blue)"
            status_text = f"📉 原油下跌 ({station_name} {base_price}c / 原油跌 {abs(oil_change)}%)"
            desc = f"<strong>{station_name}</strong>（{station_address}）目前 U91 現價為 <strong>{base_price} c/L</strong>。國際原油成本回落，短期內暴漲風險低。"
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
            status_text = f"🟢 走勢平穩 ({station_name} 現價 {base_price} c/L)"
            desc = f"<strong>{station_name}</strong>（{station_address}）目前 U91 現價為 <strong>{base_price} c/L</strong>。國際原油走勢平穩 ({oil_change:+.1f}%)，價格波動溫和。"
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

    # C. 打包寫入 data.json
    data = {
        "last_updated": time_str,
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
            "retail_prices": [round(p, 1) for p in retail_curve],
            "oil_costs": oil_cost_curve,
            "scores": scores_curve,
        },
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    analyze_and_generate()
