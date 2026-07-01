"""
有明倉庫 レオシス ペットフード在庫取得スクリプト
使い方: python pet_stock_fetcher.py
→ stock_data.json を生成します
"""

import requests
import json
import re
from datetime import datetime
from urllib.parse import quote

BASE_URL = "https://reosys2.kanda-web.co.jp/LOGIME"
USER_ID = "555"
PASSWORD = "555"

# 取得する商品コード（直接指定）
TARGET_CODES = ["e0780", "e0781", "e0782", "e0783", "e0784", "e0785"]


def clean_html(text):
    """HTMLタグと_WHSCD_INHABIT_を除去"""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("_WHSCD_INHABIT_", "").strip()
    return text


def login(session):
    """レオシスにログイン"""
    # ログインページ取得
    session.get(BASE_URL + "/Home?DBINF=LMEP")

    # ChkLogin
    session.headers.update({"X-Requested-With": "XMLHttpRequest"})
    r = session.post(
        BASE_URL + "/P3AS/P3AS0000/ChkLogin/",
        data=f"USERID={quote(quote(USER_ID))}&USERPASS={quote(quote(PASSWORD))}",
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    res = r.json()
    if res.get("iRes") != 0:
        raise Exception(f"ChkLogin失敗: {res}")

    # Login
    session.headers.pop("X-Requested-With", None)
    r2 = session.post(
        BASE_URL + "/P3AS/P3AS0000/Login",
        data={
            "SelCopCd": "",
            "BrowserInfo": "",
            "LoginId": quote(USER_ID),
            "LoginPass": quote(PASSWORD),
            "P3VALUECWData.LOGINURL": BASE_URL + "/Home?DBINF=LMEP",
        },
    )
    if "/P3AS0010/" not in r2.url:
        raise Exception("ログイン失敗: リダイレクト先が想定外")

    # 在庫ページ初期化
    session.get(BASE_URL + "/P3TZ/P3TZ0010/P3TZ0010WC")
    session.headers.update({"X-Requested-With": "XMLHttpRequest"})
    print("ログイン成功")


def fetch_stock_by_code(session, code):
    """商品コードで在庫を1件取得して返す"""
    data = {
        "VendorCD": "1353",
        "WarehouseCD": "10",
        "PurchaseCD": "",
        "MerchandiseCD": code,
        "CodeType": "",
        "SearchCodeCD": "",
        "MerchandiseName": "",
        "SearchLot": "",
        "SearchExpiryFom": "",
        "SearchExpiryTo": "",
        "ExistenceClassListHidden": "100,200,300,400,500,",
        "CheckNotInStock": "true",
        "DisplayType": "false",
        "ShowFreeTp": "",
        "ShowAcquireTp": "",
        "CheckSTOCK_CTL": "true",
        "page": "1",
        "rp": "10",
        "sortname": "Code",
        "sortorder": "asc",
    }
    r = session.post(
        BASE_URL + "/P3TZ/P3TZ0010/StockList",
        data=data,
        headers={
            "Referer": BASE_URL + "/P3TZ/P3TZ0010/P3TZ0010WC",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
    )
    return r.json().get("rows", [])


def parse_rows(rows):
    """行データをパースして辞書リストに変換"""
    results = []
    for row in rows:
        c = [clean_html(x) for x in row["cell"]]
        # 数値変換（カンマ区切りに対応）
        def to_int(s):
            try:
                return int(s.replace(",", ""))
            except (ValueError, AttributeError):
                return 0

        good_stock = to_int(c[7])   # 良品在庫(A)
        reserved   = to_int(c[4])   # 指示済数(B)
        ordered    = to_int(c[5])   # 受注残数(C)
        real_stock = good_stock - reserved - ordered  # 正しい在庫

        results.append({
            "code":        c[0],
            "name":        c[1],
            "show_code":   c[2],
            "current":     to_int(c[3]),  # 現在庫数
            "good_stock":  good_stock,    # A: 良品在庫
            "reserved":    reserved,      # B: 指示済数
            "ordered":     ordered,       # C: 受注残数
            "real_stock":  real_stock,    # A-B-C: 正しい在庫
            "return_stock": to_int(c[8]), # 返品在庫
        })
    return results


def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    })

    login(session)

    unique = []
    for code in TARGET_CODES:
        rows = fetch_stock_by_code(session, code)
        parsed = parse_rows(rows)
        if parsed:
            unique.append(parsed[0])
            print(f"  {code} → {parsed[0]['name']}")
        else:
            print(f"  {code} → データなし")

    output = {
        "updated_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "items": unique,
    }

    with open("stock_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n完了: {len(unique)}商品 → stock_data.json に保存しました")
    print(f"更新日時: {output['updated_at']}")


if __name__ == "__main__":
    main()
