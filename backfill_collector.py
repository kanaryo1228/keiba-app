import re
import time
import sqlite3
import datetime
import requests
from bs4 import BeautifulSoup

def run_backfill(days_back=30):
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS board_learning_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT UNIQUE,
            horse_name TEXT,
            rank INTEGER,
            is_board INTEGER,
            waku INTEGER,
            hana_score REAL,
            weight_ratio REAL,
            paddock_score REAL,
            is_top_jockey INTEGER,
            odds REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    top_jockeys = ["笹川翼", "矢野貴", "御神本", "吉原寛", "森泰斗", "本田重", "山崎誠", "赤岡修", "吉村智", "新原勇", "和田譲", "岡部誠", "下原理"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    now = datetime.datetime.now()
    target_dates = [(now - datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(1, days_back + 1)]

    print(f"==================================================")
    print(f"【過去{days_back}日間】の地方競馬レースを徹底探索します...")
    print(f"期間: {target_dates[-1]} 〜 {target_dates[0]}")
    print(f"==================================================")

    all_race_ids = []
    for idx, d_str in enumerate(target_dates):
        api_url = f"https://nar.netkeiba.com/top/race_list_sub.html?kaisai_date={d_str}"
        try:
            r = requests.get(api_url, headers=headers, timeout=5)
            if r.status_code == 200:
                r.encoding = r.apparent_encoding or "utf-8"
                found = re.findall(r"race_id=(\d{12})", r.text)
                for rid in found:
                    if rid not in all_race_ids:
                        all_race_ids.append(rid)
        except Exception:
            pass
        if (idx + 1) % 5 == 0:
            print(f"  カレンダー探索進捗: {idx + 1}/{days_back} 日完了 (実在レース {len(all_race_ids)} 件発見)")

    print(f"\n[探索完了] 過去{days_back}日間で合計 {len(all_race_ids)} 件の確定レースを特定しました！")
    print("データ抽出を開始します（サーバー負荷防止のため安全ウェイトを挟みます）...\n")

    total_added = 0
    # 最大150レース分を重点サンプリング（約1,500〜2,000頭の極上データセット）
    target_sample = all_race_ids[:150]

    for i, rid in enumerate(target_sample):
        res_url = f"https://nar.netkeiba.com/race/result.html?race_id={rid}"
        try:
            res = requests.get(res_url, headers=headers, timeout=5)
            if res.status_code != 200:
                continue
            res.encoding = res.apparent_encoding or "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")

            rows = soup.find_all("tr", class_=re.compile(r"ResultList|data_row"))
            if not rows:
                for tbl in soup.find_all("table"):
                    cand = tbl.find_all("tr")
                    if len(cand) >= 5:
                        rows = cand
                        break

            race_added = 0
            for row in rows:
                text = row.get_text()
                if "着順" in text or "馬名" in text:
                    continue

                tds = row.find_all("td")
                if len(tds) < 5:
                    continue

                rank_cell = row.find(class_=re.compile(r"Rank|rank"))
                rank_val = None
                if rank_cell and rank_cell.text.strip().isdigit():
                    rank_val = int(rank_cell.text.strip())
                else:
                    for td in tds:
                        val = td.text.strip()
                        if val.isdigit() and int(val) <= 20:
                            rank_val = int(val)
                            break
                if rank_val is None:
                    continue

                is_board = 1 if rank_val <= 5 else 0

                name_cell = row.find(class_=re.compile(r"HorseName|horse_name|bamei"))
                if name_cell:
                    horse_name = name_cell.text.strip()
                else:
                    a_tag = row.find("a", href=re.compile(r"/horse/"))
                    horse_name = a_tag.text.strip() if a_tag else "出走馬"

                waku_cell = row.find(class_=re.compile(r"Waku|waku"))
                waku = int(waku_cell.text.strip()) if (waku_cell and waku_cell.text.strip().isdigit()) else 1

                jockey_cell = row.find(class_=re.compile(r"Jockey|jockey"))
                j_name = jockey_cell.text.strip() if jockey_cell else ""
                is_top = 1 if any(tj in j_name for tj in top_jockeys) else 0

                weight_cell = row.find(class_=re.compile(r"Weight|kinryo"))
                burden_w = 54.0
                if weight_cell:
                    wm = re.search(r"(\d{2}(?:\.\d)?)", weight_cell.text)
                    if wm: burden_w = float(wm.group(1))

                hana = 40.0
                corner_cell = row.find(class_=re.compile(r"Pass|Corner"))
                if corner_cell:
                    cm = re.search(r"^(\d{1,2})", corner_cell.text.strip())
                    if cm:
                        p = int(cm.group(1))
                        hana = 90.0 if p == 1 else (70.0 if p <= 3 else 25.0)

                b_wt = 480.0
                pad_score = 0.0
                diff_m = re.search(r"(\d{3})\(([\+\-]?\d+)\)", row.text)
                if diff_m:
                    b_wt = float(diff_m.group(1))
                    diff_val = int(diff_m.group(2))
                    if diff_val >= 14 or diff_val <= -12:
                        pad_score = -2.0
                    elif -4 <= diff_val <= +4:
                        pad_score = 1.0

                weight_ratio = round(burden_w / b_wt, 4)

                odds = 10.0
                odds_cell = row.find(class_=re.compile(r"Odds|odds"))
                if odds_cell:
                    om = re.search(r"(\d+(?:\.\d+)?)", odds_cell.text)
                    if om: odds = float(om.group(1))

                unique_key = f"{rid}_{horse_name}"
                try:
                    cur.execute("""
                        INSERT OR IGNORE INTO board_learning_logs (race_id, horse_name, rank, is_board, waku, hana_score, weight_ratio, paddock_score, is_top_jockey, odds)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (unique_key, horse_name, rank_val, is_board, waku, hana, weight_ratio, pad_score, is_top, odds))
                    race_added += 1
                except Exception:
                    pass

            total_added += race_added
            if (i + 1) % 10 == 0 or (i + 1) == len(target_sample):
                print(f"  [{i + 1}/{len(target_sample)} レース処理] 累計蓄積数: {total_added} 頭")
            
            # アクセス過多防止の安全ウェイト（0.4秒）
            time.sleep(0.4)
        except Exception:
            continue

    conn.commit()
    conn.close()
    print(f"\n==================================================")
    print(f"【バックフィル完了】計 {total_added} 頭分の確定実績データを新たに獲得しました！")
    print(f"==================================================")

if __name__ == "__main__":
    run_backfill(days_back=30)
