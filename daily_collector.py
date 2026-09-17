import re
import sqlite3
import datetime
import requests
from bs4 import BeautifulSoup

def collect_real_nar_data():
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS board_learning_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id TEXT,
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

    top_jockeys = ["笹川翼", "矢野貴", "御神本", "吉原寛", "森泰斗", "本田重", "山崎誠", "赤岡修", "吉村智", "新原勇", "和田譲"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 直近3日間の開催日程
    now = datetime.datetime.now()
    target_dates = [(now - datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(1, 4)]
    
    race_ids = set()
    print(f"実在レースURLを探索中... 対象日: {', '.join(target_dates)}")

    # netkeiba NARの動的データ供給エンドポイント (race_list_sub.html) を直接取得
    for d_str in target_dates:
        api_url = f"https://nar.netkeiba.com/top/race_list_sub.html?kaisai_date={d_str}"
        try:
            r = requests.get(api_url, headers=headers, timeout=5)
            if r.status_code == 200:
                r.encoding = r.apparent_encoding or "utf-8"
                found = re.findall(r"race_id=(\d{12})", r.text)
                for rid in found:
                    race_ids.add(rid)
        except Exception:
            continue

    print(f"[発見] 実在する直近の確定レースID: {len(race_ids)} 件")
    if not race_ids:
        print("レースIDが見つかりませんでした。通信環境を確認してください。")
        conn.close()
        return

    collected_horses = 0
    # 直近レースから順番にスクレイピング（最大20レース = 約200〜250頭分）
    for rid in list(race_ids)[:20]:
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

            race_horses_count = 0
            for row in rows:
                text = row.get_text()
                if "着順" in text or "馬名" in text:
                    continue

                tds = row.find_all("td")
                if len(tds) < 5:
                    continue

                # 着順
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

                # 馬名
                name_cell = row.find(class_=re.compile(r"HorseName|horse_name|bamei"))
                if name_cell:
                    horse_name = name_cell.text.strip()
                else:
                    a_tag = row.find("a", href=re.compile(r"/horse/"))
                    horse_name = a_tag.text.strip() if a_tag else "出走馬"

                # 枠番
                waku_cell = row.find(class_=re.compile(r"Waku|waku"))
                waku = int(waku_cell.text.strip()) if (waku_cell and waku_cell.text.strip().isdigit()) else 1

                # 騎手
                jockey_cell = row.find(class_=re.compile(r"Jockey|jockey"))
                j_name = jockey_cell.text.strip() if jockey_cell else ""
                is_top = 1 if any(tj in j_name for tj in top_jockeys) else 0

                # 斤量
                weight_cell = row.find(class_=re.compile(r"Weight|kinryo"))
                burden_w = 54.0
                if weight_cell:
                    wm = re.search(r"(\d{2}(?:\.\d)?)", weight_cell.text)
                    if wm: burden_w = float(wm.group(1))

                # 通過順位からハナ度
                hana = 40.0
                corner_cell = row.find(class_=re.compile(r"Pass|Corner"))
                if corner_cell:
                    cm = re.search(r"^(\d{1,2})", corner_cell.text.strip())
                    if cm:
                        p = int(cm.group(1))
                        hana = 90.0 if p == 1 else (70.0 if p <= 3 else 25.0)

                # 馬体重
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

                # オッズ
                odds = 10.0
                odds_cell = row.find(class_=re.compile(r"Odds|odds"))
                if odds_cell:
                    om = re.search(r"(\d+(?:\.\d+)?)", odds_cell.text)
                    if om: odds = float(om.group(1))

                cur.execute("""
                    INSERT INTO board_learning_logs (race_id, horse_name, rank, is_board, waku, hana_score, weight_ratio, paddock_score, is_top_jockey, odds)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (rid, horse_name, rank_val, is_board, waku, hana, weight_ratio, pad_score, is_top, odds))
                collected_horses += 1
                race_horses_count += 1

            if race_horses_count > 0:
                print(f"  -> レースID {rid} から {race_horses_count} 頭の確定データを取得")
        except Exception as e:
            continue

    conn.commit()
    conn.close()
    print(f"\n[収集成功] 実際の地方競馬レース結果から計 {collected_horses} 頭分のリアル生データをDBへ保存しました！")

if __name__ == "__main__":
    collect_real_nar_data()
