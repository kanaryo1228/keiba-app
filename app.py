import re
import csv
import io
import json
import sqlite3
import requests
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

TOP_JOCKEYS = [
    "笹川翼", "矢野貴", "御神本", "吉原寛", "森泰斗", "本田重", 
    "山崎誠", "町田直", "和田譲", "赤岡修", "宮川実", "山本聡", 
    "高松亮", "村上忍", "岡部誠", "下原理", "吉村智", "新原勇"
]

def init_db():
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS race_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_name TEXT,
            venue_info TEXT,
            strategy TEXT,
            honmei TEXT,
            ana TEXT,
            recommended_bet TEXT,
            result_rank TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

HTML_CONTENT = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>地方競馬 AI予想ダッシュボード PRO MAX</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        let timer = null;
        function toggleAutoRefresh(cb) {{
            if (cb.checked) {{
                timer = setInterval(() => {{
                    const form = document.getElementById("race-form");
                    if (form) form.submit();
                }}, 30000);
            }} else {{
                if (timer) clearInterval(timer);
            }}
        }}
    </script>
</head>
<body class="bg-slate-100 min-h-screen text-slate-800 antialiased pb-16">
    <header class="bg-slate-900 text-white py-3 border-b border-slate-700 shadow-sm sticky top-0 z-50">
        <div class="max-w-6xl mx-auto px-4 flex justify-between items-center">
            <div>
                <h1 class="text-xl font-black tracking-wide text-emerald-400 flex items-center gap-2">
                    <span>🏇</span> KEIBA-AI PRO MAX
                </h1>
                <p class="text-xs text-slate-400">ハナ奪取指数 & 勝負気配 & トラックバイアスエンジン</p>
            </div>
            <div class="flex items-center gap-3">
                <label class="flex items-center gap-1 text-xs text-slate-300 font-bold cursor-pointer">
                    <input type="checkbox" onchange="toggleAutoRefresh(this)" class="rounded text-emerald-500">
                    <span>30秒自動更新</span>
                </label>
                <span class="text-xs bg-slate-800 border border-slate-600 text-slate-300 px-2.5 py-1 rounded-full font-bold">
                    {strategy_badge}
                </span>
            </div>
        </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-6 space-y-6">
        <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
            <h3 class="text-sm font-bold text-slate-700 mb-3 flex items-center gap-1.5">
                <span>⚙️</span> レースURL / ID と 予想戦略
            </h3>
            <form id="race-form" method="post" action="/fetch" class="space-y-3">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
                    <input type="text" name="race_url" placeholder="出馬表URL または 12桁のレースID" 
                           value="{current_url}"
                           class="md:col-span-2 px-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500">
                    
                    <select name="strategy" class="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-slate-50 font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500">
                        <option value="balanced" {sel_strat_bal}>戦略: ⚖️ バランス (能力重視)</option>
                        <option value="safe" {sel_strat_safe}>戦略: 🎯 的中重視 (軸馬厳選)</option>
                        <option value="aggressive" {sel_strat_agg}>戦略: 🔥 配当重視 (盲点穴特化)</option>
                    </select>
                </div>
                <div class="flex justify-between items-center pt-1">
                    <div class="text-[11px] text-slate-500">
                        ※レースID入力で同日前半レースのバイアス・馬体重・ハナ奪取度を完全解析
                    </div>
                    <button type="submit" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-6 py-2 rounded-lg text-sm transition shadow-sm flex items-center gap-1">
                        <span>⚡️</span> AI最先端解析実行
                    </button>
                </div>
            </form>
        </div>

        <div class="bg-gradient-to-r from-slate-900 to-slate-800 text-white rounded-xl p-4 shadow-sm border border-slate-700">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div>
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-[10px] bg-emerald-500 text-slate-950 font-black px-2 py-0.5 rounded">本日バイアス判定</span>
                        <span class="text-xs font-bold text-slate-300">{bias_race_count_text}</span>
                    </div>
                    <h3 class="text-lg font-black text-white">{bias_summary_headline}</h3>
                    <p class="text-xs text-slate-400 mt-0.5">{bias_detail_text}</p>
                </div>
                <div class="flex gap-2">
                    <div class="bg-slate-800/80 border border-slate-600 rounded-lg px-3 py-1.5 text-center min-w-[90px]">
                        <div class="text-[10px] text-slate-400">内枠(1~3)率</div>
                        <div class="text-base font-black text-emerald-400">{inner_waku_rate}%</div>
                    </div>
                    <div class="bg-slate-800/80 border border-slate-600 rounded-lg px-3 py-1.5 text-center min-w-[90px]">
                        <div class="text-[10px] text-slate-400">先行・逃げ率</div>
                        <div class="text-base font-black text-amber-400">{front_rate}%</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 flex flex-col justify-between">
                <div>
                    <div class="flex flex-wrap gap-1.5 items-center mb-1">
                        <span class="text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">{venue_info}</span>
                        <span class="text-xs font-bold text-purple-700 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded">{strategy_title}</span>
                    </div>
                    <h2 class="text-2xl font-black text-slate-900 mt-1">{race_name}</h2>
                    <div class="text-[11px] text-slate-500 mt-1">{pace_analysis_comment}</div>
                </div>
                <div class="mt-4 pt-3 border-t border-slate-100 text-xs space-y-1">
                    <div>能力本命: <strong class="text-slate-900 font-bold text-sm">{honmei}</strong></div>
                    <div>厳選穴馬: <strong class="text-amber-700 font-bold">{ana_horses}</strong></div>
                </div>
            </div>

            <div class="md:col-span-2 bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-5 shadow-sm">
                <div class="flex justify-between items-center mb-2">
                    <h3 class="font-extrabold text-amber-950 text-sm flex items-center gap-1.5">
                        <span>🎯</span> AI推奨 最適資金配分買い目 ({strategy_title})
                    </h3>
                    <form method="post" action="/save-history" class="inline">
                        <input type="hidden" name="race_name" value="{race_name}">
                        <input type="hidden" name="venue_info" value="{venue_info}">
                        <input type="hidden" name="strategy" value="{strategy_title}">
                        <input type="hidden" name="honmei" value="{honmei}">
                        <input type="hidden" name="ana" value="{ana_horses}">
                        <input type="hidden" name="recommended_bet" value="{bet_primary}">
                        <button type="submit" class="bg-amber-600 hover:bg-amber-700 text-white font-bold px-3 py-1 rounded text-xs transition shadow-sm">
                            💾 履歴に保存
                        </button>
                    </form>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                    <div class="bg-white/90 rounded-lg p-3 border border-amber-200 shadow-sm">
                        <div class="font-bold text-slate-600 mb-1">【主軸勝負】</div>
                        <div class="text-amber-950 font-black text-sm">{bet_primary}</div>
                        <div class="text-slate-600 mt-1 text-[11px]">{bet_primary_sub}</div>
                    </div>
                    <div class="bg-white/90 rounded-lg p-3 border border-amber-200 shadow-sm">
                        <div class="font-bold text-slate-600 mb-1">【連系推奨】</div>
                        <div class="text-slate-800 font-bold">{bet_secondary}</div>
                        <div class="text-amber-900 font-extrabold mt-1">三連複: {bet_sanrenpuku}</div>
                    </div>
                    <div class="bg-white/90 rounded-lg p-3 border border-amber-200 shadow-sm">
                        <div class="font-bold text-slate-600 mb-1">【波乱狙い】</div>
                        <div class="text-amber-900 font-extrabold text-[11px] leading-tight">{bet_sanrentan}</div>
                        <p class="text-[11px] text-slate-500 mt-1">{bet_note}</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-x-auto">
            <table class="w-full text-left text-sm whitespace-nowrap">
                <thead class="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">
                    <tr>
                        <th class="py-3 px-3 text-center w-10">印</th>
                        <th class="py-3 px-3 text-center w-10">枠</th>
                        <th class="py-3 px-3 text-center w-10">馬番</th>
                        <th class="py-3 px-4">馬名 / 前走情報</th>
                        <th class="py-3 px-3">騎手 / 斤量</th>
                        <th class="py-3 px-3 text-center">ハナ奪取度</th>
                        <th class="py-3 px-3 text-center">パドック気配</th>
                        <th class="py-3 px-3 text-center">勝負補正</th>
                        <th class="py-3 px-3 text-right">実質能力</th>
                        <th class="py-3 px-3 text-right">オッズ</th>
                        <th class="py-3 px-3 text-right">勝率</th>
                        <th class="py-3 px-3 text-right">期待値</th>
                        <th class="py-3 px-4 text-center">判定</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                    {table_rows}
                </tbody>
            </table>
        </div>

        <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-3 gap-2">
                <div>
                    <h3 class="font-bold text-slate-800 text-base flex items-center gap-2">
                        <span>📊</span> 収支履歴シミュレーター
                    </h3>
                    <p class="text-xs text-slate-500">保存した推奨馬券の累積勝率・回収率</p>
                </div>
                <div class="flex items-center gap-2">
                    <a href="/export-csv" class="bg-slate-700 hover:bg-slate-800 text-white font-bold px-3 py-1.5 rounded-lg text-xs transition flex items-center gap-1 shadow-sm">
                        <span>📥</span> 履歴CSV出力
                    </a>
                    <div class="bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-1 text-center">
                        <div class="text-[10px] text-emerald-600 font-bold">的中率</div>
                        <div class="text-sm font-black text-emerald-700">{sim_win_rate}%</div>
                    </div>
                    <div class="bg-amber-50 border border-amber-200 rounded-lg px-3 py-1 text-center">
                        <div class="text-[10px] text-amber-600 font-bold">回収率</div>
                        <div class="text-sm font-black text-amber-800">{sim_recovery_rate}%</div>
                    </div>
                </div>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs whitespace-nowrap">
                    <thead class="bg-slate-50 text-slate-500 font-bold border-b border-slate-200">
                        <tr>
                            <th class="py-2 px-3">レース名</th>
                            <th class="py-2 px-3">戦略</th>
                            <th class="py-2 px-3">本命 / 穴馬</th>
                            <th class="py-2 px-3">推奨買い目</th>
                            <th class="py-2 px-3">結果入力</th>
                            <th class="py-2 px-3 text-center">操作</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
                        {history_rows}
                    </tbody>
                </table>
            </div>
        </div>
    </main>
</body>
</html>
"""

def crawl_today_bias(race_id_str: str):
    if not race_id_str or len(race_id_str) != 12:
        return {
            "race_count": 0,
            "inner_rate": 45.0,
            "front_rate": 60.0,
            "headline": "コース標準バイアス適用中",
            "detail": "レースIDを指定すると同日前半レースの結果から自動算出されます",
            "inner_bonus": 1.0,
            "front_bonus": 1.5
        }

    base_id = race_id_str[:10]
    current_race_num = int(race_id_str[10:12])
    
    inner_top3_count = 0
    front_top3_count = 0
    total_top3_count = 0
    analyzed_races = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    start_r = max(1, current_race_num - 5)
    for r_num in range(start_r, current_race_num):
        target_id = f"{base_id}{r_num:02d}"
        url = f"https://nar.netkeiba.com/race/result.html?race_id={target_id}"
        try:
            res = requests.get(url, headers=headers, timeout=2.5)
            if res.status_code != 200:
                continue
            res.encoding = res.apparent_encoding or "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            
            rows = soup.find_all("tr", class_=re.compile(r"ResultList|data_row"))
            if not rows:
                continue

            analyzed_races += 1
            rank_found = 0
            for row in rows:
                rank_cell = row.find(class_=re.compile(r"Rank|rank"))
                if not rank_cell or not rank_cell.text.strip().isdigit():
                    continue
                rank = int(rank_cell.text.strip())
                if rank in [1, 2, 3]:
                    rank_found += 1
                    total_top3_count += 1
                    
                    waku_cell = row.find(class_=re.compile(r"Waku|waku"))
                    if waku_cell and waku_cell.text.strip().isdigit():
                        if int(waku_cell.text.strip()) in [1, 2, 3]:
                            inner_top3_count += 1
                    
                    corner_cell = row.find(class_=re.compile(r"Pass|Corner|corner"))
                    if corner_cell:
                        c_text = corner_cell.text.strip()
                        m = re.search(r"^(\d{1,2})", c_text)
                        if m and int(m.group(1)) <= 4:
                            front_top3_count += 1

                if rank_found >= 3:
                    break
        except Exception:
            continue

    if total_top3_count == 0:
        return {
            "race_count": 0,
            "inner_rate": 42.0,
            "front_rate": 58.0,
            "headline": "基準トラックバイアス適用中",
            "detail": "本日前半レースの確定前、または第1Rのため標準バイアスをセットしています。",
            "inner_bonus": 0.8,
            "front_bonus": 1.2
        }

    inner_rate = round(inner_top3_count / total_top3_count * 100, 1)
    front_rate = round(front_top3_count / total_top3_count * 100, 1)

    inner_bonus = 2.5 if inner_rate >= 55.0 else (-1.5 if inner_rate <= 25.0 else 0.5)
    w_text = "極端な内枠天国" if inner_rate >= 55.0 else ("外枠有利・外差し傾向" if inner_rate <= 25.0 else "内外フラット")

    front_bonus = 2.8 if front_rate >= 65.0 else (-1.5 if front_rate <= 35.0 else 1.0)
    p_text = "前残り・逃げ先行超有利" if front_rate >= 65.0 else ("外差し・追込決着優勢" if front_rate <= 35.0 else "先行標準有利")

    return {
        "race_count": analyzed_races,
        "inner_rate": inner_rate,
        "front_rate": front_rate,
        "headline": f"本日傾向: 【{w_text}】×【{p_text}】",
        "detail": f"直前{analyzed_races}Rのデータから集計。内枠率{inner_rate}%、先行通過率{front_rate}%。",
        "inner_bonus": inner_bonus,
        "front_bonus": front_bonus
    }

def parse_netkeiba_race(input_text: str):
    race_id_match = re.search(r"(\d{12})", input_text)
    race_id_str = race_id_match.group(1) if race_id_match else ""

    if race_id_str:
        target_url = f"https://nar.netkeiba.com/race/shutuba.html?race_id={race_id_str}"
    else:
        target_url = input_text

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        resp = requests.get(target_url, headers=headers, timeout=6)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None, "通信エラー", "接続できませんでした", ""

    r_name = soup.find(class_=re.compile(r"RaceName|Race_Name"))
    race_name = r_name.text.strip() if r_name else "地方競馬 出馬表"

    r_data = soup.find(class_=re.compile(r"RaceData01|RaceData"))
    venue_info = r_data.text.strip() if r_data else "地方競馬 ダート"

    horses = []
    rows = soup.find_all("tr", class_=re.compile(r"HorseList|data_row"))
    if not rows:
        for tbl in soup.find_all("table"):
            candidate_rows = tbl.find_all("tr")
            if len(candidate_rows) >= 5:
                rows = candidate_rows
                break

    for row in rows:
        text = row.get_text()
        if "馬番" in text or "馬名" in text:
            continue

        tds = row.find_all("td")
        if len(tds) < 5:
            continue

        try:
            umaban_cell = row.find(class_=re.compile(r"Umaban|umaban"))
            if not umaban_cell:
                nums = [td.text.strip() for td in tds if td.text.strip().isdigit()]
                umaban = int(nums[0]) if nums else len(horses) + 1
            else:
                umaban = int(re.search(r"\d+", umaban_cell.text).group())

            waku_cell = row.find(class_=re.compile(r"Waku|waku"))
            waku = waku_cell.text.strip() if waku_cell else "-"

            name_cell = row.find(class_=re.compile(r"HorseName|horse_name|bamei"))
            if not name_cell:
                a_tag = row.find("a", href=re.compile(r"/horse/"))
                horse_name = a_tag.text.strip() if a_tag else "出走馬"
            else:
                horse_name = name_cell.text.strip()

            jockey_cell = row.find(class_=re.compile(r"Jockey|jockey|kishu"))
            jockey = jockey_cell.text.strip() if jockey_cell else "騎手"
            jockey = re.sub(r"[\r\n\t\s]+", " ", jockey)

            weight_cell = row.find(class_=re.compile(r"Weight|weight|kinryo"))
            burden_weight = 54.0
            if weight_cell:
                w_match = re.search(r"(\d{2}(?:\.\d)?)", weight_cell.text)
                if w_match:
                    burden_weight = float(w_match.group(1))

            odds_cell = row.find(class_=re.compile(r"Popular|odds|ninki"))
            odds = 12.0
            if odds_cell:
                o_match = re.search(r"(\d+(?:\.\d+)?)", odds_cell.text)
                if o_match:
                    val = float(o_match.group(1))
                    if val > 1.0:
                        odds = val

            paddock_sign = "良好"
            paddock_score = 0.0
            horse_weight_text = "-"
            horse_body_weight = 480
            for td in tds:
                m = re.search(r"(\d{3})\(([\+\-]?\d+)\)", td.text)
                if m:
                    w_val = int(m.group(1))
                    diff = int(m.group(2))
                    horse_body_weight = w_val
                    horse_weight_text = f"{w_val}({diff:+d})"
                    if diff >= 14:
                        paddock_sign = "太め注意"
                        paddock_score = -2.0
                    elif diff <= -12:
                        paddock_sign = "大幅減"
                        paddock_score = -2.2
                    elif -4 <= diff <= +4:
                        paddock_sign = "仕上がり良好"
                        paddock_score = +1.0
                    break

            running_style = "自在"
            hana_score = 40
            past_jockey = ""
            past_cells = row.find_all(class_=re.compile(r"Past|past|Zen|Result"))
            past_summary = "前走: データ集計中"
            
            if past_cells:
                past_text = past_cells[0].text.strip()
                rank_m = re.search(r"(\d{1,2})着", past_text)
                if rank_m:
                    past_summary = f"前走: {rank_m.group(1)}着"
                
                corner_m = re.search(r"(\d{1,2})-(\d{1,2})", past_text)
                if corner_m:
                    first_pos = int(corner_m.group(1))
                    if first_pos == 1:
                        running_style = "逃げ"
                        hana_score = 85
                    elif first_pos <= 3:
                        running_style = "先行"
                        hana_score = 65
                    elif first_pos >= 8:
                        running_style = "追込"
                        hana_score = 15
                    else:
                        running_style = "差し"
                        hana_score = 30

                for tj in TOP_JOCKEYS:
                    if tj in past_text:
                        past_jockey = tj
                        break

            if waku in ["1", "2"]:
                hana_score += 10

            is_jockey_upgrade = False
            current_is_top = any(tj in jockey for tj in TOP_JOCKEYS)
            if current_is_top and (not past_jockey or past_jockey not in TOP_JOCKEYS):
                is_jockey_upgrade = True

            base_speed = 80.0
            if "1着" in past_summary:
                base_speed += 3.5
            elif "2着" in past_summary or "3着" in past_summary:
                base_speed += 1.8
            elif "着外" in past_summary or "8着" in past_summary:
                base_speed -= 1.5

            horses.append({
                "waku": waku,
                "umaban": umaban,
                "horse_name": horse_name,
                "jockey": jockey,
                "burden_weight": burden_weight,
                "horse_body_weight": horse_body_weight,
                "odds": odds,
                "horse_weight_text": horse_weight_text,
                "paddock_sign": paddock_sign,
                "paddock_score": paddock_score,
                "running_style": running_style,
                "hana_score": min(95, hana_score),
                "is_jockey_upgrade": is_jockey_upgrade,
                "past_summary": past_summary,
                "base_speed_idx": base_speed
            })
        except Exception:
            continue

    if not horses:
        return None, race_name, venue_info, race_id_str
    return pd.DataFrame(horses), race_name, venue_info, race_id_str

def get_default_nar_data():
    return pd.DataFrame([
        {"waku": "1", "umaban": 1, "horse_name": "ミックファイア", "jockey": "御神本", "burden_weight": 57.0, "horse_body_weight": 495, "odds": 3.2, "horse_weight_text": "495(+2)", "paddock_sign": "仕上がり良好", "paddock_score": 1.0, "running_style": "先行", "hana_score": 75, "is_jockey_upgrade": False, "base_speed_idx": 86.5, "past_summary": "前走: 1着 (重賞GP)"},
        {"waku": "2", "umaban": 2, "horse_name": "ヒーローコール", "jockey": "森泰斗", "burden_weight": 57.0, "horse_body_weight": 482, "odds": 4.5, "horse_weight_text": "482(0)", "paddock_sign": "仕上がり良好", "paddock_score": 1.0, "running_style": "逃げ", "hana_score": 90, "is_jockey_upgrade": False, "base_speed_idx": 85.0, "past_summary": "前走: 2着 (戸塚記念)"},
        {"waku": "3", "umaban": 3, "horse_name": "マンダリンヒーロー", "jockey": "矢野貴", "burden_weight": 57.0, "horse_body_weight": 478, "odds": 8.8, "horse_weight_text": "478(-2)", "paddock_sign": "仕上がり良好", "paddock_score": 1.0, "running_style": "差し", "hana_score": 35, "is_jockey_upgrade": True, "base_speed_idx": 84.0, "past_summary": "前走: 3着 (黒潮盃)"},
        {"waku": "4", "umaban": 4, "horse_name": "ライトウォーリア", "jockey": "吉原寛", "burden_weight": 57.0, "horse_body_weight": 504, "odds": 14.2, "horse_weight_text": "504(+14)", "paddock_sign": "太め注意", "paddock_score": -2.0, "running_style": "先行", "hana_score": 60, "is_jockey_upgrade": False, "base_speed_idx": 82.5, "past_summary": "前走: 1着 (埼玉新聞栄冠)"},
        {"waku": "5", "umaban": 5, "horse_name": "ギガキング", "jockey": "和田譲", "burden_weight": 57.0, "horse_body_weight": 490, "odds": 22.0, "horse_weight_text": "490(+4)", "paddock_sign": "良好", "paddock_score": 0.5, "running_style": "差し", "hana_score": 30, "is_jockey_upgrade": False, "base_speed_idx": 82.0, "past_summary": "前走: 4着 (報知グランプリ)"},
        {"waku": "6", "umaban": 6, "horse_name": "カジノフォンテン", "jockey": "本田重", "burden_weight": 57.0, "horse_body_weight": 512, "odds": 38.5, "horse_weight_text": "512(-12)", "paddock_sign": "大幅減", "paddock_score": -2.2, "running_style": "先行", "hana_score": 50, "is_jockey_upgrade": False, "base_speed_idx": 78.0, "past_summary": "前走: 6着 (勝島王冠)"},
        {"waku": "7", "umaban": 7, "horse_name": "セイカメテオポリス", "jockey": "笹川翼", "burden_weight": 57.0, "horse_body_weight": 488, "odds": 18.0, "horse_weight_text": "488(+2)", "paddock_sign": "仕上がり良好", "paddock_score": 1.0, "running_style": "追込", "hana_score": 15, "is_jockey_upgrade": True, "base_speed_idx": 83.5, "past_summary": "前走: 2着 (東京記念)"},
        {"waku": "8", "umaban": 8, "horse_name": "スワーヴアラミス", "jockey": "町田直", "burden_weight": 57.0, "horse_body_weight": 496, "odds": 52.0, "horse_weight_text": "496(+1)", "paddock_sign": "良好", "paddock_score": 0.0, "running_style": "差し", "hana_score": 25, "is_jockey_upgrade": False, "base_speed_idx": 77.0, "past_summary": "前走: 8着 (ゴールドC)"},
    ]), "大井11R 東京大賞典 (JpnⅠ)", "大井 ダート2000m", "202444091311"

def apply_dynamic_learning_bias(df: pd.DataFrame, bias_data: dict):
    df["speed_idx"] = df["base_speed_idx"].copy()
    df["bonus_tags"] = ""

    for idx, row in df.iterrows():
        bonus = 0.0
        tags = []

        h_score = row.get("hana_score", 40)
        if h_score >= 80:
            bonus += 2.4
            tags.append("ハナ濃厚")
        elif h_score >= 65:
            bonus += 1.2
            tags.append("好位先行")

        if row.get("is_jockey_upgrade", False):
            bonus += 2.0
            tags.append("勝負鞍上")

        b_wt = row.get("horse_body_weight", 480)
        k_wt = row.get("burden_weight", 54.0)
        if b_wt > 0:
            ratio = k_wt / b_wt
            if ratio >= 0.123 and b_wt <= 445:
                bonus -= 1.8
                tags.append("斤量酷")

        waku = str(row.get("waku", "0"))
        if waku in ["1", "2", "3"]:
            bonus += bias_data["inner_bonus"]
            if bias_data["inner_bonus"] >= 2.0:
                tags.append("本日内枠利")
        elif waku in ["7", "8"] and bias_data["inner_bonus"] < 0:
            bonus += 2.0
            tags.append("本日外差し利")

        style = row.get("running_style", "")
        if "逃げ" in style or "先行" in style:
            bonus += bias_data["front_bonus"]
            if bias_data["front_bonus"] >= 2.0:
                tags.append("本日前利")

        p_score = row.get("paddock_score", 0.0)
        bonus += p_score
        if p_score >= 1.0:
            tags.append("パドック良")
        elif p_score <= -2.0:
            tags.append(row.get("paddock_sign", "気配割"))

        df.at[idx, "speed_idx"] = round(row["base_speed_idx"] + bonus, 1)
        df.at[idx, "bonus_tags"] = " ".join(tags)

    return df

def evaluate_dataframe(df: pd.DataFrame, strategy: str, bias_data: dict):
    df = apply_dynamic_learning_bias(df, bias_data)

    if strategy == "safe":
        scores = (
            (df["speed_idx"] - 75.0) * 0.80 
            - (df["burden_weight"] - 55.0) * 0.25 
            - np.log(df["odds"]) * 0.60
        ).to_numpy()
        scaled = scores / 1.4
    elif strategy == "aggressive":
        scores = (
            (df["speed_idx"] - 75.0) * 0.70 
            - (df["burden_weight"] - 55.0) * 0.20 
            - np.log(df["odds"]) * 0.25
        ).to_numpy()
        scaled = scores / 1.6
    else:
        scores = (
            (df["speed_idx"] - 75.0) * 0.75 
            - (df["burden_weight"] - 55.0) * 0.25 
            - np.log(df["odds"]) * 0.40
        ).to_numpy()
        scaled = scores / 1.5

    exps = np.exp(scaled - np.max(scaled))
    raw_win_prob = exps / np.sum(exps)
    
    df["win_prob"] = raw_win_prob
    df["ev"] = df["win_prob"] * df["odds"] * 0.80

    df = df.sort_values(by="win_prob", ascending=False).reset_index(drop=True)
    marks = ["◎", "◯", "▲", "△", "△"] + [""] * max(0, len(df) - 5)
    df["mark"] = marks[:len(df)]

    return df

def get_history_and_simulation():
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    cur.execute("SELECT id, race_name, strategy, honmei, ana, recommended_bet, result_rank FROM race_history ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    total_races = 0
    wins = 0
    total_spent = 0
    total_return = 0

    history_html = []
    for r in rows:
        r_id, r_name, strat, h_mei, ana, rec_bet, res_rank = r
        total_races += 1

        odds_match = re.search(r"(\d+(?:\.\d+)?)倍", rec_bet)
        odds_val = float(odds_match.group(1)) if odds_match else 2.8

        if res_rank == "1着的中":
            wins += 1
            total_spent += 1000
            total_return += int(1000 * odds_val)
        elif res_rank in ["複勝的中", "ワイド的中"]:
            wins += 1
            total_spent += 1000
            total_return += int(1000 * max(1.5, odds_val * 0.4))
        elif res_rank == "不的中":
            total_spent += 1000

        history_html.append(f"""
        <tr>
            <td class="py-2.5 px-3 font-bold text-slate-800">{r_name}</td>
            <td class="py-2.5 px-3"><span class="bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-bold">{strat}</span></td>
            <td class="py-2.5 px-3 font-bold text-emerald-700">{h_mei}<br><span class="text-amber-700 font-normal">穴: {ana}</span></td>
            <td class="py-2.5 px-3 font-mono">{rec_bet}</td>
            <td class="py-2.5 px-3">
                <form method="post" action="/update-result" class="flex gap-1 items-center">
                    <input type="hidden" name="race_id" value="{r_id}">
                    <select name="result_rank" class="border border-slate-300 rounded px-1.5 py-0.5 text-xs bg-slate-50 font-bold">
                        <option value="" {"selected" if not res_rank else ""}>未確定</option>
                        <option value="1着的中" {"selected" if res_rank=="1着的中" else ""}>🎯 1着的中</option>
                        <option value="複勝的中" {"selected" if res_rank=="複勝的中" else ""}>✅ 複勝的中</option>
                        <option value="ワイド的中" {"selected" if res_rank=="ワイド的中" else ""}>✅ ワイド的中</option>
                        <option value="不的中" {"selected" if res_rank=="不的中" else ""}>❌ 不的中</option>
                    </select>
                    <button type="submit" class="bg-slate-700 text-white px-2 py-0.5 rounded text-[10px]">反映</button>
                </form>
            </td>
            <td class="py-2.5 px-3 text-center">
                <form method="post" action="/delete-history" onsubmit="return confirm('削除しますか？');">
                    <input type="hidden" name="race_id" value="{r_id}">
                    <button type="submit" class="text-rose-500 hover:text-rose-700 font-bold text-[11px]">削除</button>
                </form>
            </td>
        </tr>
        """)

    win_rate = round((wins / total_races * 100), 1) if total_races > 0 else 0.0
    recovery_rate = round((total_return / total_spent * 100), 1) if total_spent > 0 else 0.0

    if not history_html:
        history_html = ['<tr><td colspan="6" class="text-center py-4 text-slate-400">履歴はまだありません。「履歴に保存」を押すと登録されます。</td></tr>']

    return "".join(history_html), win_rate, recovery_rate

def build_view(df: pd.DataFrame, race_name: str, venue_info: str, race_id_str: str = "", strategy: str = "balanced", current_url: str = ""):
    # 初期トップ画面（空）のときは外部通信をスキップして即座に初期画面を表示
    if not current_url and not race_id_str:
        bias_data = {
            "race_count": 0,
            "inner_rate": 45.0,
            "front_rate": 60.0,
            "headline": "コース標準バイアス待機中",
            "detail": "出馬表URLまたはレースIDを入力して「AI解析実行」を押してください",
            "inner_bonus": 1.0,
            "front_bonus": 1.5
        }
    else:
        bias_data = crawl_today_bias(race_id_str)

    df = evaluate_dataframe(df, strategy, bias_data)

    honmei_row = df.iloc[0]
    honmei = f"({honmei_row['umaban']}) {honmei_row['horse_name']}"

    speed_threshold = df["speed_idx"].median()
    ana_candidate_df = df[
        (df["odds"] >= 6.0) & 
        (df["odds"] <= 45.0) & 
        (df["win_prob"] >= 0.055) & 
        (df["ev"] >= 0.95) & 
        (df["speed_idx"] >= speed_threshold) &
        (df["umaban"] != honmei_row["umaban"])
    ].sort_values(by="ev", ascending=False)

    ana_top_list = ana_candidate_df.head(2)
    if len(ana_top_list) > 0:
        ana_horses = ", ".join([f"({r['umaban']}) {r['horse_name']}" for _, r in ana_top_list.iterrows()])
    else:
        ana_horses = "該当なし (オッズ相応)"

    opponents = df.iloc[1:5]["umaban"].tolist()

    if strategy == "safe":
        strategy_title = "的中重視"
        strategy_badge = "🎯 的中重視"
        bet_primary = f"複勝/ワイド軸: 馬番 {honmei_row['umaban']} ({honmei_row['odds']}倍)"
        bet_primary_sub = "ハナ濃厚・バイアス合致の実力最上位軸"
        bet_secondary = f"ワイド流し: {honmei_row['umaban']} ＝ {opponents[0]}, {opponents[1]}"
        bet_sanrenpuku = f"{honmei_row['umaban']} ＝ {opponents[0]} ＝ {opponents[1]}"
        bet_sanrentan = f"馬単: [{honmei_row['umaban']}] ⇄ [{opponents[0]}]"
        bet_note = "手堅い着内狙い"
    elif strategy == "aggressive":
        strategy_title = "配当重視"
        strategy_badge = "🔥 配当重視"
        ana_target = ana_top_list.iloc[0] if len(ana_top_list) > 0 else df.iloc[1]
        bet_primary = f"単勝/複勝: 馬番 {ana_target['umaban']} ({ana_target['odds']}倍)"
        bet_primary_sub = "勝負気配・先行力十分の厳選穴馬"
        bet_secondary = f"ワイド: {honmei_row['umaban']} ＝ {ana_target['umaban']}"
        bet_sanrenpuku = f"{ana_target['umaban']} ＝ {honmei_row['umaban']} ＝ {opponents[0]}, {opponents[1]}"
        bet_sanrentan = f"1着: [{ana_target['umaban']}]<br>2着: [{honmei_row['umaban']},{opponents[0]}]<br>3着: [{honmei_row['umaban']},{','.join(map(str, opponents[:3]))}]"
        bet_note = "勝負気配の穴頭狙い"
    else:
        strategy_title = "バランス"
        strategy_badge = "⚖️ バランス"
        bet_primary = f"単勝: 馬番 {honmei_row['umaban']} ({honmei_row['odds']}倍)"
        bet_primary_sub = "ハナ奪取度＋実質能力の真の本命"
        bet_secondary = f"馬連: {honmei_row['umaban']} － {', '.join(map(str, opponents[:3]))}"
        bet_sanrenpuku = f"{honmei_row['umaban']} ＝ {', '.join(map(str, opponents[:4]))}"
        o1, o2 = opponents[0], opponents[1]
        bet_sanrentan = f"1着: [{honmei_row['umaban']}]<br>2着: [{o1},{o2}]<br>3着: [{o1},{o2},{','.join(map(str, opponents[2:4]))}]"
        bet_note = "能力上位フォーメーション"

    ana_umaban_set = set(ana_top_list["umaban"].tolist()) if len(ana_top_list) > 0 else set()

    rows_html = []
    for _, row in df.sort_values(by="umaban").iterrows():
        ev = row["ev"]
        odds = row["odds"]
        prob = row["win_prob"]
        u_num = row["umaban"]

        badge_class = ""
        if u_num in ana_umaban_set:
            badge = '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-black bg-amber-500 text-white shadow-sm">★ 厳選妙味穴馬</span>'
            badge_class = 'bg-amber-50/50'
        elif u_num == honmei_row["umaban"]:
            badge = '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-600 text-white shadow-sm">◎ 能力本命</span>'
        elif odds <= 3.5 and prob < 0.16:
            badge = '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-700 border border-rose-200">▲ 危険人気</span>'
        elif ev >= 0.85 and odds >= 5.0:
            badge = '<span class="text-xs text-slate-500 font-bold">△ 抑え</span>'
        else:
            badge = '<span class="text-xs text-slate-300 font-mono">―</span>'

        ev_color = "text-amber-600 font-black" if u_num in ana_umaban_set else ("text-emerald-600 font-bold" if ev >= 0.85 else "text-slate-400")
        mark_color = "text-rose-600" if row["mark"] == "◎" else ("text-blue-600" if row["mark"] == "◯" else "text-amber-600")

        h_score = row.get("hana_score", 40)
        h_color = "text-emerald-600 font-black" if h_score >= 80 else ("text-slate-700 font-bold" if h_score >= 60 else "text-slate-400")

        p_sign = row.get("paddock_sign", "-")
        if "良" in p_sign:
            paddock_badge = f'<span class="bg-emerald-50 border border-emerald-200 text-emerald-700 text-[10px] font-bold px-1.5 py-0.5 rounded">{row.get("horse_weight_text", "-")}<br>{p_sign}</span>'
        elif "減" in p_sign or "注" in p_sign or "割" in p_sign:
            paddock_badge = f'<span class="bg-rose-50 border border-rose-200 text-rose-700 text-[10px] font-bold px-1.5 py-0.5 rounded">{row.get("horse_weight_text", "-")}<br>{p_sign}</span>'
        else:
            paddock_badge = f'<span class="text-slate-500 font-mono text-[11px]">{row.get("horse_weight_text", "-")}</span>'

        bonus_tags_html = ""
        if row["bonus_tags"]:
            for t in row["bonus_tags"].split():
                color = "bg-rose-50 text-rose-700 border-rose-200" if "減" in t or "注" in t or "割" in t or "酷" in t else "bg-emerald-50 text-emerald-700 border-emerald-200"
                bonus_tags_html += f'<span class="{color} border text-[10px] font-bold px-1 rounded">{t}</span> '
        else:
            bonus_tags_html = '<span class="text-slate-300">-</span>'

        rows_html.append(f"""
        <tr class="hover:bg-slate-50 transition {badge_class}">
            <td class="py-3 px-3 text-center font-black text-base {mark_color}">{row["mark"]}</td>
            <td class="py-3 px-3 text-center font-mono text-slate-500">{row.get("waku", "-")}</td>
            <td class="py-3 px-3 text-center font-mono font-bold text-slate-700">{row["umaban"]}</td>
            <td class="py-3 px-4">
                <div class="font-bold text-slate-900">{row["horse_name"]}</div>
                <div class="text-[11px] text-slate-500">{row.get("past_summary", "前走データなし")} ({row.get("running_style", "自在")})</div>
            </td>
            <td class="py-3 px-3 text-slate-600">{row["jockey"]} ({row["burden_weight"]}kg)</td>
            <td class="py-3 px-3 text-center font-mono text-xs {h_color}">{h_score}%</td>
            <td class="py-3 px-3 text-center">{paddock_badge}</td>
            <td class="py-3 px-3 text-center">{bonus_tags_html}</td>
            <td class="py-3 px-3 text-right font-mono text-slate-800 font-bold text-base">{row["speed_idx"]:.1f}</td>
            <td class="py-3 px-3 text-right font-mono font-bold">{row["odds"]:.1f}倍</td>
            <td class="py-3 px-3 text-right font-mono text-slate-700">{row["win_prob"]*100:.1f}%</td>
            <td class="py-3 px-3 text-right font-mono text-base {ev_color}">{ev:.2f}</td>
            <td class="py-3 px-4 text-center">{badge}</td>
        </tr>
        """)

    history_rows, win_rate, recovery_rate = get_history_and_simulation()

    return HTML_CONTENT.format(
        table_rows="".join(rows_html),
        ana_horses=ana_horses,
        honmei=honmei,
        bet_primary=bet_primary,
        bet_primary_sub=bet_primary_sub,
        bet_secondary=bet_secondary,
        bet_sanrenpuku=bet_sanrenpuku,
        bet_sanrentan=bet_sanrentan,
        bet_note=bet_note,
        race_name=race_name,
        venue_info=venue_info,
        bias_race_count_text=f"直前{bias_data['race_count']}R解析済" if bias_data['race_count'] > 0 else "初期待機中",
        bias_summary_headline=bias_data["headline"],
        bias_detail_text=bias_data["detail"],
        inner_waku_rate=bias_data["inner_rate"],
        front_rate=bias_data["front_rate"],
        pace_analysis_comment="出走表入力でリアルタイム解析が実行されます",
        strategy_title=strategy_title,
        strategy_badge=strategy_badge,
        sel_strat_bal="selected" if strategy == "balanced" else "",
        sel_strat_safe="selected" if strategy == "safe" else "",
        sel_strat_agg="selected" if strategy == "aggressive" else "",
        current_url=current_url,
        history_rows=history_rows,
        sim_win_rate=win_rate,
        sim_recovery_rate=recovery_rate
    )

@app.get("/", response_class=HTMLResponse)
def index():
    df, race_name, venue_info, race_id_str = get_default_nar_data()
    return build_view(df, race_name, venue_info, race_id_str="")

@app.post("/fetch", response_class=HTMLResponse)
def fetch_race(race_url: str = Form(...), strategy: str = Form("balanced")):
    if not race_url.strip():
        df, race_name, venue_info, race_id_str = get_default_nar_data()
        return build_view(df, race_name, venue_info, race_id_str="", strategy=strategy)
    
    df, race_name, venue_info, race_id_str = parse_netkeiba_race(race_url.strip())
    if df is None:
        df, race_name, venue_info, race_id_str = get_default_nar_data()
        race_name = f"【取得エラー: サンプル表示中】{race_name}"
    return build_view(df, race_name, venue_info, race_id_str=race_id_str, strategy=strategy, current_url=race_url)

@app.post("/save-history")
def save_history(
    race_name: str = Form(...),
    venue_info: str = Form(...),
    strategy: str = Form(...),
    honmei: str = Form(...),
    ana: str = Form(...),
    recommended_bet: str = Form(...)
):
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO race_history (race_name, venue_info, strategy, honmei, ana, recommended_bet)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (race_name, venue_info, strategy, honmei, ana, recommended_bet))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/update-result")
def update_result(race_id: int = Form(...), result_rank: str = Form(...)):
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    cur.execute("UPDATE race_history SET result_rank = ? WHERE id = ?", (result_rank, race_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete-history")
def delete_history(race_id: int = Form(...)):
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM race_history WHERE id = ?", (race_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/export-csv")
def export_csv():
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    cur.execute("SELECT id, race_name, venue_info, strategy, honmei, ana, recommended_bet, result_rank, created_at FROM race_history ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "レース名", "条件", "戦略", "本命", "穴馬", "推奨買い目", "結果", "記録日時"])
    for r in rows:
        writer.writerow(r)

    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=keiba_ai_history.csv"
    return response
