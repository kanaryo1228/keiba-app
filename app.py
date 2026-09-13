import re
import json
import sqlite3
import requests
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

# 履歴・シミュレーション用DB初期化
def init_db():
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS race_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            race_name TEXT,
            venue_info TEXT,
            honmei TEXT,
            ana TEXT,
            tansho_bet TEXT,
            sanrenpuku_bet TEXT,
            sanrentan_bet TEXT,
            result_rank TEXT DEFAULT '',
            memo TEXT DEFAULT '',
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
    <title>地方競馬 AI予想ダッシュボード</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100 min-h-screen text-slate-800 antialiased pb-16">
    <header class="bg-slate-900 text-white py-4 border-b border-slate-700 shadow-sm sticky top-0 z-50">
        <div class="max-w-6xl mx-auto px-4 flex justify-between items-center">
            <div>
                <h1 class="text-xl font-black tracking-wide text-emerald-400 flex items-center gap-2">
                    <span>🏇</span> KEIBA-AI PRO
                </h1>
                <p class="text-xs text-slate-400">リアルタイム出馬表解析 & 期待値最適化エンジン</p>
            </div>
            <div class="flex items-center gap-2">
                <span class="text-xs bg-emerald-950 border border-emerald-500 text-emerald-300 px-3 py-1 rounded-full font-bold">
                    PRO Live
                </span>
            </div>
        </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-6 space-y-6">
        <!-- URL & 馬場入力 -->
        <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
            <h3 class="text-sm font-bold text-slate-700 mb-3 flex items-center gap-1.5">
                <span>⚙️</span> 出馬表URL / レースID と 馬場条件の指定
            </h3>
            <form method="post" action="/fetch" class="space-y-3">
                <div class="flex flex-col md:flex-row gap-2">
                    <input type="text" name="race_url" placeholder="例: https://nar.netkeiba.com/race/shutuba.html?race_id=... または 12桁のID" 
                           value="{current_url}"
                           class="flex-1 px-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500">
                    
                    <select name="track_condition" class="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-slate-50 font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500">
                        <option value="良" {selected_ryo}>馬場: 良 (標準)</option>
                        <option value="稍重" {selected_yaya}>馬場: 稍重 (+前残り)</option>
                        <option value="重" {selected_zyu}>馬場: 重 (+高速前有利)</option>
                        <option value="不良" {selected_furyo}>馬場: 不良 (+内・前特化)</option>
                    </select>

                    <button type="submit" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-6 py-2 rounded-lg text-sm transition shadow-sm">
                        AI解析実行
                    </button>
                </div>
            </form>
        </div>

        <!-- サマリー -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 flex flex-col justify-between">
                <div>
                    <div class="flex gap-2 items-center mb-1">
                        <span class="text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">{venue_info}</span>
                        <span class="text-xs font-bold text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded">馬場: {track_condition}</span>
                    </div>
                    <h2 class="text-2xl font-black text-slate-900 mt-1">{race_name}</h2>
                </div>
                <div class="mt-4 pt-3 border-t border-slate-100 text-xs">
                    本命: <strong class="text-slate-900 font-bold">{honmei}</strong><br>
                    穴馬: <strong class="text-amber-700 font-bold">{ana_horses}</strong>
                </div>
            </div>

            <!-- 推奨買い目ボックス（単勝・馬連・ワイド・三連複・三連単） -->
            <div class="md:col-span-2 bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-5 shadow-sm">
                <div class="flex justify-between items-center mb-2">
                    <h3 class="font-extrabold text-amber-950 text-sm flex items-center gap-1.5">
                        <span>🎯</span> AI推奨 最適資金配分買い目
                    </h3>
                    <form method="post" action="/save-history" class="inline">
                        <input type="hidden" name="race_name" value="{race_name}">
                        <input type="hidden" name="venue_info" value="{venue_info}">
                        <input type="hidden" name="honmei" value="{honmei}">
                        <input type="hidden" name="ana" value="{ana_horses}">
                        <input type="hidden" name="tansho_bet" value="{bet_tansho}">
                        <input type="hidden" name="sanrenpuku_bet" value="{bet_sanrenpuku}">
                        <input type="hidden" name="sanrentan_bet" value="{bet_sanrentan}">
                        <input type="hidden" name="current_url" value="{current_url}">
                        <button type="submit" class="bg-amber-600 hover:bg-amber-700 text-white font-bold px-3 py-1 rounded text-xs transition shadow-sm">
                            💾 このレースを履歴に保存
                        </button>
                    </form>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                    <div class="bg-white/90 rounded-lg p-3 border border-amber-200 shadow-sm">
                        <div class="font-bold text-slate-600 mb-1">【単勝 / 馬連】</div>
                        <div class="text-amber-900 font-extrabold">{bet_tansho}</div>
                        <div class="text-slate-700 mt-1">馬連: <strong class="font-bold">{bet_umaren}</strong></div>
                    </div>
                    <div class="bg-white/90 rounded-lg p-3 border border-amber-200 shadow-sm">
                        <div class="font-bold text-slate-600 mb-1">【ワイド / 三連複】</div>
                        <div class="text-slate-700">ワイド: <strong class="font-bold">{bet_wide}</strong></div>
                        <div class="text-amber-900 font-extrabold mt-1">三連複: {bet_sanrenpuku}</div>
                        <p class="text-[11px] text-slate-500 mt-0.5">本命軸 相手流し</p>
                    </div>
                    <div class="bg-white/90 rounded-lg p-3 border border-amber-200 shadow-sm">
                        <div class="font-bold text-slate-600 mb-1">【三連単フォーメーション】</div>
                        <div class="text-amber-900 font-extrabold text-[11px] leading-tight">{bet_sanrentan}</div>
                        <p class="text-[11px] text-slate-500 mt-1">EV重視の絞り込み</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- メイン出走表 -->
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-x-auto">
            <table class="w-full text-left text-sm whitespace-nowrap">
                <thead class="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase">
                    <tr>
                        <th class="py-3 px-3 text-center w-10">印</th>
                        <th class="py-3 px-3 text-center w-10">枠</th>
                        <th class="py-3 px-3 text-center w-10">馬番</th>
                        <th class="py-3 px-4">馬名 / 前走</th>
                        <th class="py-3 px-3">騎手 / 斤量</th>
                        <th class="py-3 px-3 text-right">推定指数</th>
                        <th class="py-3 px-3 text-right">単勝オッズ</th>
                        <th class="py-3 px-3 text-right">予測勝率</th>
                        <th class="py-3 px-3 text-right">期待値 (EV)</th>
                        <th class="py-3 px-4 text-center">AI判定</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                    {table_rows}
                </tbody>
            </table>
        </div>

        <!-- 回収率シミュレーター & 保存済み履歴セクション -->
        <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-3 gap-2">
                <div>
                    <h3 class="font-bold text-slate-800 text-base flex items-center gap-2">
                        <span>📊</span> 保存済みレース履歴 & 回収率シミュレーター
                    </h3>
                    <p class="text-xs text-slate-500">保存したレースの結果（本命着順）を入力すると回収率をリアルタイム集計します</p>
                </div>
                <!-- シミュレーション集計バッジ -->
                <div class="flex gap-2">
                    <div class="bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-1 text-center">
                        <div class="text-[10px] text-emerald-600 font-bold">本命勝率</div>
                        <div class="text-sm font-black text-emerald-700">{sim_win_rate}%</div>
                    </div>
                    <div class="bg-amber-50 border border-amber-200 rounded-lg px-3 py-1 text-center">
                        <div class="text-[10px] text-amber-600 font-bold">本命単勝回収率</div>
                        <div class="text-sm font-black text-amber-800">{sim_recovery_rate}%</div>
                    </div>
                </div>
            </div>

            <!-- 履歴テーブル -->
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs whitespace-nowrap">
                    <thead class="bg-slate-50 text-slate-500 font-bold border-b border-slate-200">
                        <tr>
                            <th class="py-2 px-3">レース名</th>
                            <th class="py-2 px-3">本命 / 穴馬</th>
                            <th class="py-2 px-3">単勝推奨</th>
                            <th class="py-2 px-3">三連複推奨</th>
                            <th class="py-2 px-3">実際の結果入力</th>
                            <th class="py-2 px-3">メモ</th>
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

def parse_netkeiba_race(input_text: str):
    race_id_match = re.search(r"(\d{12})", input_text)
    if race_id_match:
        target_url = f"https://nar.netkeiba.com/race/shutuba.html?race_id={race_id_match.group(1)}"
    else:
        target_url = input_text

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        resp = requests.get(target_url, headers=headers, timeout=10)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None, "通信エラー", "接続できませんでした"

    r_name = soup.find(class_=re.compile(r"RaceName|Race_Name"))
    race_name = r_name.text.strip() if r_name else "地方競馬 出馬表"

    r_data = soup.find(class_=re.compile(r"RaceData01|RaceData"))
    venue_info = r_data.text.strip() if r_data else "地方競馬 ダート"

    horses = []
    rows = soup.find_all("tr", class_=re.compile(r"HorseList|data_row"))
    
    if not rows:
        tables = soup.find_all("table")
        for tbl in tables:
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
            odds = 10.0
            if odds_cell:
                o_match = re.search(r"(\d+(?:\.\d+)?)", odds_cell.text)
                if o_match:
                    val = float(o_match.group(1))
                    if val > 1.0:
                        odds = val

            past_summary = "前走: データ集計中"
            past_cells = row.find_all(class_=re.compile(r"Past|past|Zen|Result"))
            if past_cells:
                past_text = past_cells[0].text.strip()
                match = re.search(r"(\d{1,2})着", past_text)
                if match:
                    past_summary = f"前走: {match.group(1)}着"

            horses.append({
                "waku": waku,
                "umaban": umaban,
                "horse_name": horse_name,
                "jockey": jockey,
                "burden_weight": burden_weight,
                "odds": odds,
                "past_summary": past_summary,
                "base_speed_idx": round(80.0 - np.log(max(odds, 1.05)) * 3.8, 1)
            })
        except Exception:
            continue

    if not horses:
        return None, race_name, venue_info
    return pd.DataFrame(horses), race_name, venue_info

def get_default_nar_data():
    return pd.DataFrame([
        {"waku": "1", "umaban": 1, "horse_name": "ミックファイア", "jockey": "御神本", "burden_weight": 57.0, "odds": 2.1, "base_speed_idx": 88.0, "past_summary": "前走: 1着 (ダービーGP)"},
        {"waku": "2", "umaban": 2, "horse_name": "ヒーローコール", "jockey": "森泰斗", "burden_weight": 57.0, "odds": 4.5, "base_speed_idx": 84.5, "past_summary": "前走: 2着 (戸塚記念)"},
        {"waku": "3", "umaban": 3, "horse_name": "マンダリンヒーロー", "jockey": "矢野貴", "burden_weight": 57.0, "odds": 5.8, "base_speed_idx": 83.0, "past_summary": "前走: 3着 (黒潮盃)"},
        {"waku": "4", "umaban": 4, "horse_name": "ライトウォーリア", "jockey": "吉原寛", "burden_weight": 57.0, "odds": 12.4, "base_speed_idx": 81.2, "past_summary": "前走: 1着 (埼玉新聞栄冠)"},
        {"waku": "5", "umaban": 5, "horse_name": "ギガキング", "jockey": "和田譲", "burden_weight": 57.0, "odds": 16.0, "base_speed_idx": 79.5, "past_summary": "前走: 4着 (報知グランプリ)"},
        {"waku": "6", "umaban": 6, "horse_name": "カジノフォンテン", "jockey": "本田重", "burden_weight": 57.0, "odds": 28.5, "base_speed_idx": 77.0, "past_summary": "前走: 6着 (勝島王冠)"},
        {"waku": "7", "umaban": 7, "horse_name": "セイカメテオポリス", "jockey": "笹川翼", "burden_weight": 57.0, "odds": 34.0, "base_speed_idx": 76.5, "past_summary": "前走: 2着 (東京記念)"},
        {"waku": "8", "umaban": 8, "horse_name": "スワーヴアラミス", "jockey": "真島大", "burden_weight": 57.0, "odds": 48.0, "base_speed_idx": 74.0, "past_summary": "前走: 8着 (ゴールドC)"},
    ]), "大井11R 東京大賞典 (JpnⅠ)", "大井 ダート2000m"

def apply_track_condition_bias(df: pd.DataFrame, condition: str):
    df["speed_idx"] = df["base_speed_idx"].copy()
    if condition in ["重", "不良"]:
        for idx, row in df.iterrows():
            waku = str(row.get("waku", "0"))
            bonus = 0.0
            if waku in ["1", "2", "3"]:
                bonus += 1.5 if condition == "重" else 2.5
            df.at[idx, "speed_idx"] = round(row["base_speed_idx"] + bonus, 1)
    elif condition == "稍重":
        for idx, row in df.iterrows():
            waku = str(row.get("waku", "0"))
            if waku in ["1", "2"]:
                df.at[idx, "speed_idx"] = round(row["base_speed_idx"] + 0.8, 1)
    return df

def evaluate_dataframe(df: pd.DataFrame, track_condition: str):
    df = apply_track_condition_bias(df, track_condition)
    scores = (
        (df["speed_idx"] - 75.0) * 0.55 
        - (df["burden_weight"] - 55.0) * 0.25 
        - np.log(df["odds"]) * 0.45
    ).to_numpy()

    scaled = scores / 1.8
    exps = np.exp(scaled - np.max(scaled))
    df["win_prob"] = exps / np.sum(exps)
    df["ev"] = df["win_prob"] * df["odds"]

    df = df.sort_values(by="ev", ascending=False).reset_index(drop=True)
    marks = ["◎", "◯", "▲", "△", "△"] + [""] * max(0, len(df) - 5)
    df["mark"] = marks[:len(df)]
    return df

def get_history_and_simulation():
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    cur.execute("SELECT id, race_name, venue_info, honmei, ana, tansho_bet, sanrenpuku_bet, sanrentan_bet, result_rank, memo FROM race_history ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    total_races = 0
    wins = 0
    total_spent = 0
    total_return = 0

    history_html = []
    for r in rows:
        r_id, r_name, v_info, h_mei, ana, t_bet, puku_bet, tan_bet, res_rank, memo = r
        total_races += 1

        # オッズ抽出（単勝計算用）
        odds_match = re.search(r"(\d+(?:\.\d+)?)倍", t_bet)
        odds_val = float(odds_match.group(1)) if odds_match else 2.0

        if res_rank == "1着":
            wins += 1
            total_spent += 1000
            total_return += int(1000 * odds_val)
        elif res_rank in ["2着", "3着", "着外"]:
            total_spent += 1000

        history_html.append(f"""
        <tr>
            <td class="py-2.5 px-3 font-bold text-slate-800">{r_name}<br><span class="text-[10px] text-slate-400 font-normal">{v_info}</span></td>
            <td class="py-2.5 px-3 font-bold text-emerald-700">{h_mei}<br><span class="text-amber-700 font-normal">穴: {ana}</span></td>
            <td class="py-2.5 px-3">{t_bet}</td>
            <td class="py-2.5 px-3 font-mono">{puku_bet}</td>
            <td class="py-2.5 px-3">
                <form method="post" action="/update-result" class="flex gap-1 items-center">
                    <input type="hidden" name="race_id" value="{r_id}">
                    <select name="result_rank" class="border border-slate-300 rounded px-1.5 py-0.5 text-xs bg-slate-50">
                        <option value="" {"selected" if not res_rank else ""}>未確定</option>
                        <option value="1着" {"selected" if res_rank=="1着" else ""}>1着 的中</option>
                        <option value="2着" {"selected" if res_rank=="2着" else ""}>2着</option>
                        <option value="3着" {"selected" if res_rank=="3着" else ""}>3着</option>
                        <option value="着外" {"selected" if res_rank=="着外" else ""}>着外</option>
                    </select>
                    <button type="submit" class="bg-slate-700 text-white px-2 py-0.5 rounded text-[10px]">保存</button>
                </form>
            </td>
            <td class="py-2.5 px-3 text-slate-500">{memo or '-'}</td>
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
        history_html = ['<tr><td colspan="7" class="text-center py-4 text-slate-400">まだ保存されたレースはありません。「このレースを履歴に保存」を押すと記録されます。</td></tr>']

    return "".join(history_html), win_rate, recovery_rate

def build_view(df: pd.DataFrame, race_name: str, venue_info: str, track_condition: str = "良", current_url: str = ""):
    df = evaluate_dataframe(df, track_condition)

    honmei_row = df.iloc[0]
    honmei = f"({honmei_row['umaban']}) {honmei_row['horse_name']}"
    
    ana_df = df[df["ev"] >= 1.15]
    ana_horses_list = [f"({r['umaban']}) {r['horse_name']}" for _, r in ana_df.iterrows() if r["horse_name"] != honmei_row["horse_name"]]
    ana_horses = ", ".join(ana_horses_list) if ana_horses_list else "該当なし"

    bet_tansho = f"馬番 {honmei_row['umaban']} ({honmei_row['odds']}倍)"
    opponents = df.iloc[1:5]["umaban"].tolist()
    bet_umaren = f"{honmei_row['umaban']} － {', '.join(map(str, opponents[:3]))}"
    
    if ana_horses_list:
        ana_top_umaban = ana_df.iloc[0]["umaban"]
        bet_wide = f"{honmei_row['umaban']} － {ana_top_umaban}"
    else:
        bet_wide = f"{honmei_row['umaban']} － {opponents[0]}"

    # 三連複（1頭軸 相手4頭流し = 6点）
    bet_sanrenpuku = f"{honmei_row['umaban']} ＝ {', '.join(map(str, opponents[:4]))}"
    
    # 三連単（1着固定フォーメーション: 1着[◎] → 2着[◯▲] → 3着[◯▲△△]）
    o1, o2 = opponents[0], opponents[1]
    o_rest = opponents[2:4]
    second_str = f"{o1},{o2}"
    third_str = f"{o1},{o2},{','.join(map(str, o_rest))}"
    bet_sanrentan = f"1着: [{honmei_row['umaban']}]<br>2着: [{second_str}]<br>3着: [{third_str}]"

    rows_html = []
    for _, row in df.sort_values(by="umaban").iterrows():
        ev = row["ev"]
        odds = row["odds"]
        prob = row["win_prob"]

        if ev >= 1.15 and 8.0 <= odds < 50.0 and prob >= 0.05:
            badge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500 text-white shadow-sm">★ 妙味穴馬</span>'
            row_bg = 'bg-amber-50/40'
        elif ev >= 1.05 and odds < 8.0:
            badge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-600 text-white shadow-sm">◎ 期待本命</span>'
            row_bg = ''
        elif prob >= 0.18 and ev < 0.85:
            badge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-700 border border-rose-200">▲ 過剰人気</span>'
            row_bg = ''
        else:
            badge = '<span class="text-xs text-slate-400 font-mono">―</span>'
            row_bg = ''

        ev_color = "text-amber-600" if ev >= 1.15 else ("text-emerald-600" if ev >= 1.0 else "text-slate-400")
        mark_color = "text-rose-600" if row["mark"] == "◎" else ("text-blue-600" if row["mark"] == "◯" else "text-amber-600")

        rows_html.append(f"""
        <tr class="hover:bg-slate-50 transition {row_bg}">
            <td class="py-3 px-3 text-center font-black text-base {mark_color}">{row["mark"]}</td>
            <td class="py-3 px-3 text-center font-mono text-slate-500">{row.get("waku", "-")}</td>
            <td class="py-3 px-3 text-center font-mono font-bold text-slate-700">{row["umaban"]}</td>
            <td class="py-3 px-4">
                <div class="font-bold text-slate-900">{row["horse_name"]}</div>
                <div class="text-[11px] text-slate-500 mt-0.5">{row.get("past_summary", "前走データなし")}</div>
            </td>
            <td class="py-3 px-3 text-slate-600">{row["jockey"]} ({row["burden_weight"]}kg)</td>
            <td class="py-3 px-3 text-right font-mono text-slate-700 font-semibold">{row["speed_idx"]:.1f}</td>
            <td class="py-3 px-3 text-right font-mono font-bold">{row["odds"]:.1f}倍</td>
            <td class="py-3 px-3 text-right font-mono text-slate-700">{row["win_prob"]*100:.1f}%</td>
            <td class="py-3 px-3 text-right font-mono font-bold text-base {ev_color}">{ev:.2f}</td>
            <td class="py-3 px-4 text-center">{badge}</td>
        </tr>
        """)

    history_rows, win_rate, recovery_rate = get_history_and_simulation()

    return HTML_CONTENT.format(
        table_rows="".join(rows_html),
        ana_horses=ana_horses,
        honmei=honmei,
        bet_tansho=bet_tansho,
        bet_umaren=bet_umaren,
        bet_wide=bet_wide,
        bet_sanrenpuku=bet_sanrenpuku,
        bet_sanrentan=bet_sanrentan,
        race_name=race_name,
        venue_info=venue_info,
        track_condition=track_condition,
        selected_ryo="selected" if track_condition == "良" else "",
        selected_yaya="selected" if track_condition == "稍重" else "",
        selected_zyu="selected" if track_condition == "重" else "",
        selected_furyo="selected" if track_condition == "不良" else "",
        current_url=current_url,
        history_rows=history_rows,
        sim_win_rate=win_rate,
        sim_recovery_rate=recovery_rate
    )

@app.get("/", response_class=HTMLResponse)
def index():
    df, race_name, venue_info = get_default_nar_data()
    return build_view(df, race_name, venue_info)

@app.post("/fetch", response_class=HTMLResponse)
def fetch_race(race_url: str = Form(...), track_condition: str = Form("良")):
    if not race_url.strip():
        df, race_name, venue_info = get_default_nar_data()
        return build_view(df, race_name, venue_info, track_condition=track_condition)
    
    df, race_name, venue_info = parse_netkeiba_race(race_url.strip())
    if df is None:
        df, race_name, venue_info = get_default_nar_data()
        race_name = f"【取得エラー: サンプル表示中】{race_name}"
    return build_view(df, race_name, venue_info, track_condition=track_condition, current_url=race_url)

@app.post("/save-history")
def save_history(
    race_name: str = Form(...),
    venue_info: str = Form(...),
    honmei: str = Form(...),
    ana: str = Form(...),
    tansho_bet: str = Form(...),
    sanrenpuku_bet: str = Form(...),
    sanrentan_bet: str = Form(...),
    current_url: str = Form("")
):
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO race_history (race_name, venue_info, honmei, ana, tansho_bet, sanrenpuku_bet, sanrentan_bet)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (race_name, venue_info, honmei, ana, tansho_bet, sanrenpuku_bet, sanrentan_bet))
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
