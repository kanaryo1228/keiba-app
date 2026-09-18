import bloodline_db
_BLOOD_CACHE = {}

def get_horse_bloodline_cached(horse_id: str):
    if not horse_id:
        return "", ""
    if horse_id in _BLOOD_CACHE:
        return _BLOOD_CACHE[horse_id]
    try:
        url = f"https://db.netkeiba.com/horse/ped/{horse_id}/"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}, timeout=2.5)
        if r.status_code == 200:
            sp = BeautifulSoup(r.content, "html.parser")
            as_ = [a.text.strip() for a in sp.select("table.blood_table a") if a.text.strip() and a.text.strip() not in ["血統", "産駒"]]
            sire = as_[0] if len(as_) >= 1 else ""
            bms = as_[3] if len(as_) >= 4 else (as_[1] if len(as_) >= 2 else "")
            _BLOOD_CACHE[horse_id] = (sire, bms)
            return sire, bms
    except Exception:
        pass
    _BLOOD_CACHE[horse_id] = ("", "")
    return "", ""

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

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.api_route("/bloodline_search", methods=["GET", "POST"], response_class=HTMLResponse)
async def bloodline_search(request: Request, venue: str = "大井", sire: str = "", bms: str = ""):
    if request.method == "POST":
        try:
            form = await request.form()
            venue = form.get("venue", venue).strip()
            sire = form.get("sire", sire).strip()
            bms = form.get("bms", bms).strip()
        except Exception:
            pass
            
    res = bloodline_db.analyze_bloodline_for_venue(sire, bms, venue)
    
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>血統診断カルテ - {res['sire']} × {res['bms']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 p-4 sm:p-8 font-sans min-h-screen flex items-center justify-center">
    <div class="max-w-md w-full bg-slate-900 border border-amber-500/40 rounded-2xl p-6 shadow-2xl space-y-4">
        <div class="flex justify-between items-center border-b border-slate-800 pb-3">
            <span class="text-xs text-amber-400 font-bold tracking-wider">🧬 新馬戦 血統カルテ診断結果</span>
            <span class="text-xs bg-amber-400 text-slate-950 font-black px-2.5 py-0.5 rounded-full">{res['venue']}</span>
        </div>
        
        <div class="text-center py-2">
            <div class="text-xs text-slate-400 mb-1">配合総合評価</div>
            <div class="text-2xl font-black text-amber-300">{res['overall_grade']}</div>
            <div class="text-xs text-emerald-400 mt-1 font-bold">{res['venue_match']}</div>
        </div>

        <div class="space-y-3 bg-slate-950/80 p-4 rounded-xl border border-slate-800 text-xs">
            <div>
                <div class="text-slate-400 font-bold mb-0.5">父 (種牡馬): <span class="text-white text-sm">{res['sire']}</span> <span class="text-amber-400 font-mono">[{res['sire_rank']}ランク]</span></div>
                <div class="text-slate-300 leading-relaxed">{res['sire_traits']}</div>
                <div class="text-[11px] text-indigo-400 mt-1">得意競馬場: {res['best_venues']}</div>
            </div>
            <hr class="border-slate-800">
            <div>
                <div class="text-slate-400 font-bold mb-0.5">母父 (BMS): <span class="text-white text-sm">{res['bms'] if res['bms'] else "未指定"}</span> <span class="text-amber-400 font-mono">[{res['bms_rank']}ランク]</span></div>
                <div class="text-slate-300 leading-relaxed">{res['bms_bonus']}</div>
            </div>
        </div>

        <button onclick="window.close()" class="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-2 rounded-lg font-bold transition">
            閉じる
        </button>
    </div>

<!-- 馬詳細・血統モーダル -->
<div id="horseDetailModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-amber-500/50 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
        <div class="flex justify-between items-center border-b border-slate-800 pb-3">
            <div>
                <span id="mUmaban" class="text-xs bg-amber-400 text-slate-950 font-black px-2 py-0.5 rounded mr-2"></span>
                <span id="mName" class="text-base font-black text-white"></span>
            </div>
            <button onclick="closeHorseModal()" class="text-slate-400 hover:text-white text-xl font-bold">&times;</button>
        </div>
        <div class="space-y-3 text-xs">
            <div class="bg-slate-950 p-3 rounded-xl border border-slate-800 flex justify-between items-center">
                <span class="text-slate-400">血統・舞台適性ランク:</span>
                <span id="mGrade" class="text-amber-300 font-black text-base"></span>
            </div>
            <div class="space-y-2 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                <div>
                    <span class="text-slate-400 font-bold">父: </span><span id="mSire" class="text-white font-bold"></span>
                    <p id="mTraits" class="text-slate-400 text-[11px] mt-0.5 leading-relaxed"></p>
                </div>
                <hr class="border-slate-800">
                <div>
                    <span class="text-slate-400 font-bold">母父: </span><span id="mBms" class="text-white font-bold"></span>
                    <p id="mBonus" class="text-slate-400 text-[11px] mt-0.5 leading-relaxed"></p>
                </div>
            </div>
            <div id="mTip" class="p-2.5 rounded-lg bg-indigo-950/50 border border-indigo-500/30 text-indigo-300 text-[11px] leading-relaxed"></div>
        </div>
        <button onclick="closeHorseModal()" class="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-2.5 rounded-lg font-bold transition">閉じる</button>
    </div>
</div>
<script src="/static/modal.js"></script>

</body>
</html>"""
    return HTMLResponse(content=html)

TOP_JOCKEYS = [
    "笹川翼", "矢野貴", "御神本", "吉原寛", "森泰斗", "本田重", 
    "山崎誠", "町田直", "和田譲", "赤岡修", "宮川実", "山本聡", 
    "高松亮", "村上忍", "岡部誠", "下原理", "吉村智", "新原勇"
]

VENUE_MAP = {
    "44": "大井", "45": "川崎", "43": "船橋", "42": "浦和",
    "50": "園田", "54": "高知", "48": "名古屋", "46": "笠松",
    "36": "門別", "30": "門別", "51": "姫路", "55": "佐賀", "35": "盛岡", "34": "水沢"
}

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
    # 競馬場別重みテーブル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS venue_custom_weights (
            venue_code TEXT,
            param_name TEXT,
            weight_val REAL,
            sample_count INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (venue_code, param_name)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def fit_weights_for_dataset(rows):
    if len(rows) < 25:
        return None
    data = np.array(rows)
    y = data[:, 0]
    X = data[:, 1:]
    X_bias = np.c_[np.ones(X.shape[0]), X]
    lambda_reg = 0.6
    try:
        w = np.linalg.inv(X_bias.T @ X_bias + lambda_reg * np.eye(X_bias.shape[1])) @ X_bias.T @ y
        return {
            "w_hana": round(float(w[1] * 10), 2),
            "w_weight_ratio": round(float(w[2] * 45), 2),
            "w_paddock": round(float(w[3]), 2),
            "w_jockey": round(float(w[4]), 2),
            "w_bias": 1.5
        }
    except Exception:
        return None

def update_all_venue_weights():
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    
    # 1. 全体モデルの学習
    cur.execute("SELECT is_board, hana_score, weight_ratio, paddock_score, is_top_jockey FROM board_learning_logs")
    all_rows = cur.fetchall()
    all_w = fit_weights_for_dataset(all_rows)
    if all_w:
        for p_name, w_val in all_w.items():
            cur.execute("""
                INSERT OR REPLACE INTO venue_custom_weights (venue_code, param_name, weight_val, sample_count)
                VALUES ('ALL', ?, ?, ?)
            """, (p_name, w_val, len(all_rows)))

    # 2. 各競馬場別モデルの学習
    cur.execute("SELECT DISTINCT substr(race_id, 5, 2) FROM board_learning_logs")
    venue_codes = [r[0] for r in cur.fetchall() if r[0]]

    trained_venues = []
    for vc in venue_codes:
        cur.execute("""
            SELECT is_board, hana_score, weight_ratio, paddock_score, is_top_jockey 
            FROM board_learning_logs 
            WHERE substr(race_id, 5, 2) = ?
        """, (vc,))
        v_rows = cur.fetchall()
        vw = fit_weights_for_dataset(v_rows)
        if vw:
            for p_name, w_val in vw.items():
                cur.execute("""
                    INSERT OR REPLACE INTO venue_custom_weights (venue_code, param_name, weight_val, sample_count)
                    VALUES (?, ?, ?, ?)
                """, (vc, p_name, w_val, len(v_rows)))
            trained_venues.append(f"{VENUE_MAP.get(vc, vc)}({len(v_rows)}頭)")

    conn.commit()
    conn.close()
    return f"全場({len(all_rows)}頭) & コース別最適化完了: {', '.join(trained_venues[:5])}..."

def get_venue_weights(venue_code: str):
    conn = sqlite3.connect("history.db")
    cur = conn.cursor()
    # 競馬場専用ウェイトを探す
    cur.execute("SELECT param_name, weight_val, sample_count FROM venue_custom_weights WHERE venue_code = ?", (venue_code,))
    rows = cur.fetchall()
    
    # なければALL（全体）を使う
    if not rows:
        cur.execute("SELECT param_name, weight_val, sample_count FROM venue_custom_weights WHERE venue_code = 'ALL'")
        rows = cur.fetchall()

    conn.close()

    default_map = {"w_hana": 2.2, "w_weight_ratio": -15.0, "w_paddock": 1.2, "w_jockey": 1.8, "w_bias": 1.5}
    sample_cnt = rows[0][2] if rows else 0
    res = {r[0]: r[1] for r in rows}
    for k, v in default_map.items():
        if k not in res:
            res[k] = v
    return res, sample_cnt

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
                <div class="flex items-center gap-2">
                    <h1 class="text-xl font-black tracking-wide text-emerald-400 flex items-center gap-2">
                        <span>🏇</span> KEIBA-AI PRO ⚡️ ULTRA
                    </h1>
                    <span class="bg-amber-400 text-slate-950 text-xs font-black px-2.5 py-1 rounded-full shadow-lg ring-2 ring-amber-300">v2.5 ULTRA (三連系特化)</span>
                </div>
                    <span>🏇</span> KEIBA-AI PRO ⚡️ ULTRA MAX
                </h1>
                <p class="text-xs text-slate-400">競馬場別マルチモデル自律学習 & 独自指数関数エンジン</p>
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
        <!-- 独自指数関数のリアルタイム係数カード -->
        <div class="bg-gradient-to-br from-indigo-950 to-slate-900 text-white rounded-xl p-4 shadow-sm border border-indigo-800">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div>
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-[10px] bg-indigo-500 text-white font-black px-2 py-0.5 rounded">{venue_model_title}</span>
                        <span class="text-xs text-indigo-300 font-mono">標本数: {venue_sample_count}頭分</span>
                    </div>
                    <div class="font-mono text-xs md:text-sm text-indigo-200 mt-1 bg-black/30 px-3 py-1.5 rounded-lg border border-indigo-900">
                        Index = {w_hana}·Hana + {w_weight}·(斤量/体重) + {w_paddock}·Pad + {w_jockey}·Joc + {w_bias}·Bias
                    </div>
                </div>
                
    <!-- 新馬戦・全場対応 血統カルテ診断バー (v2.5) -->
    <div class="mb-6 p-4 rounded-2xl bg-gradient-to-r from-amber-950/40 via-slate-900 to-indigo-950/50 border border-amber-500/40 shadow-xl">
        <div class="flex items-center gap-2 mb-3">
            <span class="text-xl">🧬</span>
            <span class="text-sm font-bold text-amber-300">新馬戦・全競馬場別 血統適性カルテ診断 (v2.5)</span>
            <span class="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2 py-0.5 rounded-full font-mono">南関4場・門別・JRA対応</span>
        </div>
        <form action="/bloodline_search" method="post" target="_blank" class="grid grid-cols-1 sm:grid-cols-4 gap-2">
            <select name="venue" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-400">
                <option value="大井">大井競馬場</option>
                <option value="川崎">川崎競馬場</option>
                <option value="船橋">船橋競馬場</option>
                <option value="浦和">浦和競馬場</option>
                <option value="門別">門別競馬場</option>
                <option value="東京">東京ダート</option>
                <option value="中山">中山ダート</option>
            </select>
            <input type="text" name="sire" placeholder="父 (例: ヘニーヒューズ)" required class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-400">
            <input type="text" name="bms" placeholder="母父 (例: サウスヴィグラス)" class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-amber-400">
            <button type="submit" class="bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-bold py-2 px-4 rounded-lg text-xs transition shadow-md flex items-center justify-center gap-1">
                <span>🔍</span> 血統適性を診断
            </button>
        </form>
    </div>
<form method="post" action="/trigger-learn" class="self-end md:self-center">
                    <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-4 py-2 rounded-lg text-xs transition shadow-sm flex items-center gap-1.5">
                        <span>🔄</span> 全競馬場一括再学習
                    </button>
                </form>
            </div>
        </div>

        <!-- 入力エリア -->
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
                        ※競馬場を自動判別し、その競馬場専用に最適化された独自指数関数で解析します
                    </div>
                    <button type="submit" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-6 py-2 rounded-lg text-sm transition shadow-sm flex items-center gap-1">
                        <span>⚡️</span> AI最先端解析実行
                    </button>
                </div>
            </form>
        </div>

        <!-- 当日トラックバイアス集計カード -->
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

        <!-- サマリー & 買い目 -->
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
                        <div class="mt-4 p-4 rounded-xl bg-slate-900 border-2 border-amber-400 text-white shadow-xl">
    <div class="text-amber-400 font-black text-sm mb-3 flex items-center gap-2">
        <span>🏆 AI厳選 三連系フォーメーション (v2.5)</span>
    </div>
    <div class="col-span-1 md:col-span-3 mt-4 space-y-3">
        <div class="bg-slate-950 p-3 rounded-lg border border-emerald-500/40">
            <div class="text-emerald-400 font-bold mb-1">【三連複 軸1頭流し】(6点)</div>
            <div class="flex flex-wrap gap-2 p-2 bg-slate-950/60 rounded-lg">{bet_sanrenpuku}</div>
        </div>
        <div class="bg-slate-950 p-3 rounded-lg border border-rose-500/40">
            <div class="text-rose-400 font-bold mb-1">【三連単 ◎1着固定】(12点)</div>
            <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 p-2 bg-slate-950/60 rounded-lg max-h-48 overflow-y-auto">{bet_sanrentan}</div>
        </div>
    </div>
</div>
                    </div>
                    <div class="bg-white/90 rounded-lg p-3 border border-amber-200 shadow-sm">
                        <div class="font-bold text-slate-600 mb-1">【波乱狙い】</div>
                        <div class="text-amber-900 font-extrabold text-[11px] leading-tight">{bet_sanrentan}</div>
                        <p class="text-[11px] text-slate-500 mt-1">{bet_note}</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- 出走表テーブル -->
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
                        <th class="py-3 px-3 text-center">コース補正</th>
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

        <!-- 履歴 & シミュレーター -->
        <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-3 gap-2">
                <div>
                    <h3 class="font-bold text-slate-800 text-base flex items-center gap-2">
                        <span>📊</span> 収支履歴シミュレーター
                    </h3>
                    <p class="text-xs text-slate-500">コース別最適化関数の累積勝率・回収率を集計中</p>
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

<!-- 馬詳細・血統モーダル -->
<div id="horseDetailModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-amber-500/50 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
        <div class="flex justify-between items-center border-b border-slate-800 pb-3">
            <div>
                <span id="mUmaban" class="text-xs bg-amber-400 text-slate-950 font-black px-2 py-0.5 rounded mr-2"></span>
                <span id="mName" class="text-base font-black text-white"></span>
            </div>
            <button onclick="closeHorseModal()" class="text-slate-400 hover:text-white text-xl font-bold">&times;</button>
        </div>
        <div class="space-y-3 text-xs">
            <div class="bg-slate-950 p-3 rounded-xl border border-slate-800 flex justify-between items-center">
                <span class="text-slate-400">血統・舞台適性ランク:</span>
                <span id="mGrade" class="text-amber-300 font-black text-base"></span>
            </div>
            <div class="space-y-2 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                <div>
                    <span class="text-slate-400 font-bold">父: </span><span id="mSire" class="text-white font-bold"></span>
                    <p id="mTraits" class="text-slate-400 text-[11px] mt-0.5 leading-relaxed"></p>
                </div>
                <hr class="border-slate-800">
                <div>
                    <span class="text-slate-400 font-bold">母父: </span><span id="mBms" class="text-white font-bold"></span>
                    <p id="mBonus" class="text-slate-400 text-[11px] mt-0.5 leading-relaxed"></p>
                </div>
            </div>
            <div id="mTip" class="p-2.5 rounded-lg bg-indigo-950/50 border border-indigo-500/30 text-indigo-300 text-[11px] leading-relaxed"></div>
        </div>
        <button onclick="closeHorseModal()" class="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-2.5 rounded-lg font-bold transition">閉じる</button>
    </div>
</div>
<script src="/static/modal.js"></script>


    <!-- AI展開・血統解説カード -->
    <div style="margin: 24px auto; max-width: 960px; padding: 22px; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 14px rgba(0,0,0,0.07); border-left: 6px solid #2563eb; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">
        <div style="font-size: 1.15rem; font-weight: bold; color: #1e293b; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.3rem;">🧠</span> AIレース展開・血統・選定理由の解説
        </div>
        <div style="font-size: 0.95rem; line-height: 1.8; color: #334155; white-space: pre-wrap; background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;">{ai_commentary}</div>
    </div>
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

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

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

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    
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
            waku = int(waku_cell.text.strip()) if (waku_cell and waku_cell.text.strip().isdigit()) else 1

            name_cell = row.find(class_=re.compile(r"HorseName|horse_name|bamei"))
            if not name_cell:
                a_tag = row.find("a", href=re.compile(r"/horse/"))
                horse_name = a_tag.text.strip() if a_tag else "出走馬"
            else:
                horse_name = name_cell.text.strip()

            jockey_cell = row.find(class_=re.compile(r"Jockey|jockey"))
            jockey = jockey_cell.text.strip() if jockey_cell else "騎手"
            jockey = re.sub(r"[\r\n\t\s]+", " ", jockey)

            weight_cell = row.find(class_=re.compile(r"Weight|weight"))
            burden_weight = 54.0
            if weight_cell:
                w_match = re.search(r"(\d{2}(?:\.\d)?)", weight_cell.text)
                if w_match:
                    burden_weight = float(w_match.group(1))

            # td[09]またはPopularセルから正確な出走前単勝オッズを取得
            odds = 99.0
            if len(tds) >= 10:
                o_str = tds[9].text.strip()
                try:
                    odds = float(o_str)
                except ValueError:
                    pass
            if odds == 99.0:
                odds_cell = row.find(class_=re.compile(r"Popular|odds"))
                if odds_cell:
                    m = re.search(r"(\d{1,3}\.\d)", odds_cell.text)
                    if m:
                        odds = float(m.group(1))

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
            hana_score = 40.0
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
                        hana_score = 85.0
                    elif first_pos <= 3:
                        running_style = "先行"
                        hana_score = 65.0
                    elif first_pos >= 8:
                        running_style = "追込"
                        hana_score = 15.0
                    else:
                        running_style = "差し"
                        hana_score = 30.0

                for tj in TOP_JOCKEYS:
                    if tj in past_text:
                        past_jockey = tj
                        break

            if waku in [1, 2]:
                hana_score += 10.0

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

                        # 血統取得と適性評価
            sire_name = ""
            bms_name = ""
            try:
                m_hid = re.search(r"/(?:horse|ped)/([0-9a-zA-Z]{10})", str(row)) or re.search(r"ketto_num=([0-9a-zA-Z]{10})", str(row))
                if m_hid:
                    sire_name, bms_name = get_horse_bloodline_cached(m_hid.group(1))
            except Exception:
                pass

            b_res = bloodline_db.analyze_bloodline_for_venue(sire_name, bms_name, venue if "venue" in locals() else "")
            blood_score = b_res.get("score", 0.0)
            blood_grade = b_res.get("overall_grade", "B")
            blood_traits = b_res.get("sire_traits", "")
            bms_bonus_desc = b_res.get("bms_bonus", "")

            horses.append({
                "waku": waku,
                "umaban": umaban,
                "horse_name": horse_name,
                "jockey": jockey,
                "burden_weight": burden_weight,
                "horse_body_weight": horse_body_weight,
                "odds": odds,
                "horse_weight_text": horse_weight_text,
                "sire": sire_name if sire_name else "血統分析中",
                "bms": bms_name if bms_name else "標準適性",
                "blood_score": blood_score,
                "blood_grade": blood_grade,
                "blood_traits": blood_traits,
                "bms_bonus": bms_bonus_desc,
                "paddock_sign": paddock_sign,
                "paddock_score": paddock_score,
                "running_style": running_style,
                "hana_score": min(95.0, hana_score),
                "is_jockey_upgrade": is_jockey_upgrade,
                "is_top_jockey": 1 if current_is_top else 0,
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
        {"waku": 1, "umaban": 1, "horse_name": "ミックファイア", "jockey": "御神本", "burden_weight": 57.0, "horse_body_weight": 495, "odds": 3.2, "horse_weight_text": "495(+2)", "paddock_sign": "仕上がり良好", "paddock_score": 1.0, "running_style": "先行", "hana_score": 75.0, "is_jockey_upgrade": False, "is_top_jockey": 1, "base_speed_idx": 86.5, "past_summary": "前走: 1着 (重賞GP)"},
        {"waku": 2, "umaban": 2, "horse_name": "ヒーローコール", "jockey": "森泰斗", "burden_weight": 57.0, "horse_body_weight": 482, "odds": 4.5, "horse_weight_text": "482(0)", "paddock_sign": "仕上がり良好", "paddock_score": 1.0, "running_style": "逃げ", "hana_score": 90.0, "is_jockey_upgrade": False, "is_top_jockey": 1, "base_speed_idx": 85.0, "past_summary": "前走: 2着 (戸塚記念)"},
        {"waku": 3, "umaban": 3, "horse_name": "マンダリンヒーロー", "jockey": "矢野貴", "burden_weight": 57.0, "horse_body_weight": 478, "odds": 8.8, "horse_weight_text": "478(-2)", "paddock_sign": "仕上がり良好", "paddock_score": 1.0, "running_style": "差し", "hana_score": 35.0, "is_jockey_upgrade": True, "is_top_jockey": 1, "base_speed_idx": 84.0, "past_summary": "前走: 3着 (黒潮盃)"},
        {"waku": 4, "umaban": 4, "horse_name": "ライトウォーリア", "jockey": "吉原寛", "burden_weight": 57.0, "horse_body_weight": 504, "odds": 14.2, "horse_weight_text": "504(+14)", "paddock_sign": "太め注意", "paddock_score": -2.0, "running_style": "先行", "hana_score": 60.0, "is_jockey_upgrade": False, "is_top_jockey": 1, "base_speed_idx": 82.5, "past_summary": "前走: 1着 (埼玉新聞栄冠)"},
        {"waku": 5, "umaban": 5, "horse_name": "ギガキング", "jockey": "和田譲", "burden_weight": 57.0, "horse_body_weight": 490, "odds": 22.0, "horse_weight_text": "490(+4)", "paddock_sign": "良好", "paddock_score": 0.5, "running_style": "差し", "hana_score": 30.0, "is_jockey_upgrade": False, "is_top_jockey": 1, "base_speed_idx": 82.0, "past_summary": "前走: 4着 (報知グランプリ)"},
        {"waku": 6, "umaban": 6, "horse_name": "カジノフォンテン", "jockey": "本田重", "burden_weight": 57.0, "horse_body_weight": 512, "odds": 38.5, "horse_weight_text": "512(-12)", "paddock_sign": "大幅減", "paddock_score": -2.2, "running_style": "先行", "hana_score": 50.0, "is_jockey_upgrade": False, "is_top_jockey": 1, "base_speed_idx": 78.0, "past_summary": "前走: 6着 (勝島王冠)"},
        {"waku": 7, "umaban": 7, "horse_name": "セイカメテオポリス", "jockey": "笹川翼", "burden_weight": 57.0, "horse_body_weight": 488, "odds": 18.0, "horse_weight_text": "488(+2)", "paddock_sign": "仕上がり良好", "paddock_score": 1.0, "running_style": "追込", "hana_score": 15.0, "is_jockey_upgrade": True, "is_top_jockey": 1, "base_speed_idx": 83.5, "past_summary": "前走: 2着 (東京記念)"},
        {"waku": 8, "umaban": 8, "horse_name": "スワーヴアラミス", "jockey": "町田直", "burden_weight": 57.0, "horse_body_weight": 496, "odds": 52.0, "horse_weight_text": "496(+1)", "paddock_sign": "良好", "paddock_score": 0.0, "running_style": "差し", "hana_score": 25.0, "is_jockey_upgrade": False, "is_top_jockey": 1, "base_speed_idx": 77.0, "past_summary": "前走: 8着 (ゴールドC)"},
    ]), "大井11R 東京大賞典 (JpnⅠ)", "大井 ダート2000m", "202444091311"

def apply_custom_formula_bias(df: pd.DataFrame, bias_data: dict, weights: dict):
    df["speed_idx"] = df["base_speed_idx"].copy()
    df["bonus_tags"] = ""

    w_hana = weights.get("w_hana", 2.2)
    w_weight = weights.get("w_weight_ratio", -15.0)
    w_pad = weights.get("w_paddock", 1.2)
    w_joc = weights.get("w_jockey", 1.8)
    w_bias = weights.get("w_bias", 1.5)

    for idx, row in df.iterrows():
        bonus = 0.0
        tags = []

        h_score = row.get("hana_score", 40.0)
        if h_score >= 80:
            bonus += (w_hana * 1.1)
            tags.append("ハナ濃厚")
        elif h_score >= 65:
            bonus += (w_hana * 0.5)
            tags.append("先行")

        b_wt = row.get("horse_body_weight", 480)
        k_wt = row.get("burden_weight", 54.0)
        ratio = (k_wt / b_wt) if b_wt > 0 else 0.11
        bonus += (ratio - 0.112) * w_weight

        p_score = row.get("paddock_score", 0.0)
        bonus += (p_score * (w_pad / 1.2))
        if p_score >= 1.0:
            tags.append("パドック良")
        elif p_score <= -2.0:
            tags.append("気配割")

        if row.get("is_jockey_upgrade", False):
            bonus += (w_joc * 1.1)
            tags.append("勝負鞍上")
        elif row.get("is_top_jockey", 0) == 1:
            bonus += (w_joc * 0.6)

        waku = int(row.get("waku", 1))

        # 新馬戦判定 & 血統ボーナス自動加算
        race_title_safe = locals().get("race_title", "") or locals().get("race_name", "") or ""
        race_name_val = str(locals().get("race_title", "") or locals().get("race_name", "") or "")
        is_shinba_race = any(k in race_name_val for k in ["新馬", "初出走", "2歳新馬", "メイクデビュー"])
        b_score = row.get("blood_score", 0.0)
        if is_shinba_race:
            # 新馬戦は過去走タイムがないため、血統適性を主軸（高ウェイト）に反映
            bonus += b_score * 1.8
            if row.get("blood_grade") in ["S+", "S", "A+"]:
                tags.append("血統特注")
        else:
            # 通常レースは適性スパイスとして加算
            bonus += b_score * 0.6
            if row.get("blood_grade") in ["S+", "S"]:
                tags.append("血統○")
        if waku in [1, 2, 3]:
            bonus += (bias_data["inner_bonus"] * (w_bias / 1.5))
            if bias_data["inner_bonus"] >= 2.0:
                tags.append("内枠利")

        df.at[idx, "speed_idx"] = round(row["base_speed_idx"] + bonus, 1)
        df.at[idx, "bonus_tags"] = " ".join(tags)

    return df

def evaluate_dataframe(df: pd.DataFrame, strategy: str, bias_data: dict, weights: dict):
    df = apply_custom_formula_bias(df, bias_data, weights)

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


def generate_ai_commentary(df, race_name, venue_info, strategy="balanced"):
    if df is None or df.empty:
        return "出走馬データが取得できませんでした。"
    
    # 印で馬を抽出
    top = df[df["mark"] == "◎"].iloc[0] if not df[df["mark"] == "◎"].empty else df.iloc[0]
    sub = df[df["mark"] == "○"].iloc[0] if not df[df["mark"] == "○"].empty else (df.iloc[1] if len(df) > 1 else None)
    ana = df[df["mark"].isin(["▲", "△"])].iloc[0] if not df[df["mark"].isin(["▲", "△"])].empty else None

    # 本命馬の評価ポイント
    top_reasons = []
    if "sire" in top and top["sire"] not in ["血統分析中", ""]:
        top_reasons.append(f"父{top['sire']}譲りのコース適性（評価: {top.get('blood_grade', 'B')}）")
    if "bonus_tags" in top and top["bonus_tags"]:
        top_reasons.append(f"『{top['bonus_tags']}』の好条件")
    if "base_speed_idx" in top:
        top_reasons.append(f"基礎指数トップクラスの実績値")
    
    top_desc = "、".join(top_reasons) if top_reasons else "総合指数の高さ"

    p1 = f"【本命の根拠】\n本命に指名した{top['umaban']}番「{top['horse_name']}」は、{top_desc}を高く評価しました。"
    if top.get("running_style"):
        p1 += f" 脚質は「{top['running_style']}」で、このコースにおける展開バイアスにも合致しています。"

    p2 = ""
    if sub is not None:
        p2 = f"\n\n【対抗・逆転候補】\n対抗の{sub['umaban']}番「{sub['horse_name']}」は安定した先行力とコース実績を保持しており、展開ひとつで首位争いに加わる有力候補です。"

    p3 = ""
    if ana is not None and ana["umaban"] != top["umaban"] and (sub is None or ana["umaban"] != sub["umaban"]):
        ana_sire = f"（父: {ana['sire']}）" if "sire" in ana and ana["sire"] not in ["血統分析中", ""] else ""
        p3 = f"\n\n【高配当の使者・穴の狙い目】\n単穴・惑星候補は{ana['umaban']}番「{ana['horse_name']}」{ana_sire}。人気薄ながら血統適性や枠順バイアスが味方しており、波乱を演出する可能性を秘めています。"

    strategy_desc = "堅実な的中重視" if strategy == "safe" else ("高回収・穴狙い" if strategy == "recovery" else "的中と配当のバランス重視")
    p4 = f"\n\n【戦略方針】\n今回は「{strategy_desc}」のロジックに基づき、期待値の高い組み合わせを中心に買い目を構築しています。"

    return f"{p1}{p2}{p3}{p4}"

def build_view(df: pd.DataFrame, race_name: str, venue_info: str, race_id_str: str = "", strategy: str = "balanced", current_url: str = ""):
    ai_commentary = generate_ai_commentary(df, race_name, venue_info, strategy)
    # 競馬場コード判定（IDの5〜6桁目、またはレース名・競馬場テキストから判定）

    # 三連系自動生成
    try:
        top_uma = [str(r['umaban']) for r in df.head(5).to_dict('records')]
        if len(top_uma) >= 5:
            # 三連複: ◎ - 相手4頭 (6点)
            f_chips = []
            for i in range(1, 5):
                for j in range(i+1, 5):
                    f_chips.append(f"""<div class='flex items-center gap-1 bg-slate-900 px-2 py-1 rounded border border-emerald-500/40 text-xs font-mono font-bold shadow-sm'><span class='w-5 h-5 flex items-center justify-center bg-emerald-500 text-slate-950 rounded-full font-black'>{top_uma[0]}</span><span class='text-slate-500'>-</span><span class='w-5 h-5 flex items-center justify-center bg-slate-800 text-emerald-300 rounded border border-slate-700'>{top_uma[i]}</span><span class='text-slate-500'>-</span><span class='w-5 h-5 flex items-center justify-center bg-slate-800 text-emerald-300 rounded border border-slate-700'>{top_uma[j]}</span></div>""")
            sanren_fuku_text = "".join(f_chips)
            bet_sanrenpuku = " | ".join([f"{top_uma[0]}-{top_uma[i]}-{top_uma[j]}" for i in range(1, 5) for j in range(i+1, 5)])
            bet_sanrenpuku = " | ".join([f"{top_uma[0]}-{top_uma[i]}-{top_uma[j]}" for i in range(1, 5) for j in range(i+1, 5)])

            # 三連単: 1着◎ -> 2着(○▲△1) -> 3着(○▲△1△2) (12点)
            t_chips = []
            for s in top_uma[1:4]:
                for t in top_uma[1:5]:
                    if s != t:
                        t_chips.append(f"""<div class='flex items-center gap-1 bg-slate-900 px-2 py-1 rounded border border-rose-500/40 text-xs font-mono font-bold shadow-sm'><span class='w-5 h-5 flex items-center justify-center bg-rose-500 text-white rounded-full font-black'>{top_uma[0]}</span><span class='text-rose-400'>→</span><span class='w-5 h-5 flex items-center justify-center bg-slate-800 text-amber-300 rounded border border-slate-700'>{s}</span><span class='text-rose-400'>→</span><span class='w-5 h-5 flex items-center justify-center bg-slate-800 text-rose-300 rounded border border-slate-700'>{t}</span></div>""")
            sanren_tan_text = "".join(t_chips)
            bet_sanrentan = " | ".join([f"{top_uma[0]}→{s}→{t}" for s in top_uma[1:4] for t in top_uma[1:5] if s != t])
            bet_sanrentan = " | ".join([f"{top_uma[0]}→{s}→{t}" for s in top_uma[1:4] for t in top_uma[1:5] if s != t])
        else:
            sanren_fuku_text = "出走数不足"
            sanren_tan_text = "出走数不足"
    except Exception:
        sanren_fuku_text = "-"
        sanren_tan_text = "-"

    venue_code = "ALL"
    if race_id_str and len(race_id_str) >= 6:
        venue_code = race_id_str[4:6]
    else:
        for vc, name in VENUE_MAP.items():
            if name in race_name or name in venue_info:
                venue_code = vc
                break

    weights, sample_count = get_venue_weights(venue_code)
    v_name = VENUE_MAP.get(venue_code, "全場共通")
    venue_model_title = f"{v_name}専用 最適化関数 F(X)" if venue_code != "ALL" else "全地方競馬 統合モデル F(X)"

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

    df = evaluate_dataframe(df, strategy, bias_data, weights)

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
        bet_primary_sub = f"{v_name}専用関数スコア最上位＋バイアス適合"
        bet_secondary = f"ワイド流し: {honmei_row['umaban']} ＝ {opponents[0]}, {opponents[1]}"
        bet_sanrenpuku = f"{honmei_row['umaban']} ＝ {opponents[0]} ＝ {opponents[1]}"
        bet_sanrentan = f"馬単: [{honmei_row['umaban']}] ⇄ [{opponents[0]}]"
        bet_note = "手堅い着内狙い"
    elif strategy == "aggressive":
        strategy_title = "配当重視"
        strategy_badge = "🔥 配当重視"
        ana_target = ana_top_list.iloc[0] if len(ana_top_list) > 0 else df.iloc[1]
        bet_primary = f"単勝/複勝: 馬番 {ana_target['umaban']} ({ana_target['odds']}倍)"
        bet_primary_sub = f"{v_name}コース適性×パドック期待値MAX穴馬"
        bet_secondary = f"ワイド: {honmei_row['umaban']} ＝ {ana_target['umaban']}"
        bet_sanrenpuku = f"{ana_target['umaban']} ＝ {honmei_row['umaban']} ＝ {opponents[0]}, {opponents[1]}"
        bet_sanrentan = f"1着: [{ana_target['umaban']}]<br>2着: [{honmei_row['umaban']},{opponents[0]}]<br>3着: [{honmei_row['umaban']},{','.join(map(str, opponents[:3]))}]"
        bet_note = "独自関数の穴頭狙い"
    else:
        strategy_title = "バランス"
        strategy_badge = "⚖️ バランス"
        bet_primary = f"単勝: 馬番 {honmei_row['umaban']} ({honmei_row['odds']}倍)"
        bet_primary_sub = f"{v_name}モデル最適化関数 F(X) 総合本命"
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

        h_score = row.get("hana_score", 40.0)
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
                color = "bg-rose-50 text-rose-700 border-rose-200" if "減" in t or "注" in t or "割" in t else "bg-indigo-50 text-indigo-700 border-indigo-200"
                bonus_tags_html += f'<span class="{color} border text-[10px] font-bold px-1 rounded">{t}</span> '
        else:
            bonus_tags_html = '<span class="text-slate-300">-</span>'

        rows_html.append(f"""
        <tr class="hover:bg-slate-50 transition {badge_class}">
            <td class="py-3 px-3 text-center font-black text-base {mark_color}">{row["mark"]}</td>
            <td class="py-3 px-3 text-center font-mono text-slate-500">{row.get("waku", "-")}</td>
            <td class="py-3 px-3 text-center font-mono font-bold text-slate-700">{row["umaban"]}</td>
            <td class="py-3 px-4">
                <div class="font-bold text-amber-300 hover:text-amber-200 cursor-pointer underline decoration-dotted flex items-center space-x-1" onclick="openHorseModal(this)" data-umaban="{row['umaban']}" data-name="{row['horse_name']}" data-sire="{row.get('sire', '未登録')}" data-bms="{row.get('bms', '未登録')}" data-grade="{row.get('blood_grade', 'B')}" data-traits="{row.get('blood_traits', '')}" data-bonus="{row.get('bms_bonus', '')}">
    <span>{row["horse_name"]}</span>
    <span class="text-[10px] text-amber-400">🔍</span>
</div>
                <div class="text-[11px] text-slate-500">{row.get("past_summary", "前走データなし")} ({row.get("running_style", "自在")})</div>
            </td>
            <td class="py-3 px-3 text-slate-600">{row["jockey"]} ({row["burden_weight"]}kg)</td>
            <td class="py-3 px-3 text-center font-mono text-xs {h_color}">{h_score:.0f}%</td>
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
        pace_analysis_comment=f"{v_name}コースの好走実績データに最適化済み",
        strategy_title=strategy_title,
        strategy_badge=strategy_badge,
        venue_model_title=venue_model_title,
        venue_sample_count=sample_count,
        w_hana=f"{weights.get('w_hana', 2.2):+.2f}",
        w_weight=f"{weights.get('w_weight_ratio', -15.0):+.1f}",
        w_paddock=f"{weights.get('w_paddock', 1.2):+.2f}",
        w_jockey=f"{weights.get('w_jockey', 1.8):+.2f}",
        w_bias=f"{weights.get('w_bias', 1.5):+.2f}",
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
    return build_view(df, race_name, venue_info, race_id_str=race_id_str)

@app.post("/fetch", response_class=HTMLResponse)
def fetch_race(race_url: str = Form(...), strategy: str = Form("balanced")):
    if not race_url.strip():
        df, race_name, venue_info, race_id_str = get_default_nar_data()
        return build_view(df, race_name, venue_info, race_id_str=race_id_str, strategy=strategy)
    
    df, race_name, venue_info, race_id_str = parse_netkeiba_race(race_url.strip())
    if df is None:
        df, race_name, venue_info, race_id_str = get_default_nar_data()
        race_name = f"【取得エラー: サンプル表示中】{race_name}"
    return build_view(df, race_name, venue_info, race_id_str=race_id_str, strategy=strategy, current_url=race_url)

@app.post("/trigger-learn")
def trigger_learn():
    update_all_venue_weights()
    return RedirectResponse(url="/", status_code=303)

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

@app.post("/api/batch-daily-learn")
def batch_daily_learn():
    msg = update_all_venue_weights()
    return {"status": "success", "message": msg}
