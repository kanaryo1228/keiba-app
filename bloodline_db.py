# 地方・中央主要ダート競馬場対応 血統マスター
SIRE_PROFILES = {
    "ヘニーヒューズ": {
        "base_rank": "S",
        "best_venues": ["大井", "船橋", "門別", "東京"],
        "traits": "新馬戦の決定打。前半から楽に前へ行ける天性のスピード。大井・船橋の平坦ワンターンは特に高連対。"
    },
    "シニスターミニスター": {
        "base_rank": "S",
        "best_venues": ["大井", "川崎", "浦和", "園田"],
        "traits": "地方砂の適性最上位。タフな馬場や小回り戦で最後までバテない驚異のスタミナとパワー。"
    },
    "サウスヴィグラス": {
        "base_rank": "S",
        "best_venues": ["浦和", "川崎", "大井", "門別"],
        "traits": "地方ダート短距離の絶対軸。スタートダッシュが速く、浦和や川崎の小回り新馬戦で先行必勝。"
    },
    "ドレフォン": {
        "base_rank": "S",
        "best_venues": ["門別", "大井", "船橋", "中山"],
        "traits": "2歳戦の仕上がりが早く素質で押し切る。門別や大井外回り1200m〜1400mの新馬戦で信頼度絶大。"
    },
    "ホッコータルマエ": {
        "base_rank": "A",
        "best_venues": ["川崎", "大井", "金沢", "盛岡"],
        "traits": "時計のかかる深いダートで本領発揮。川崎の内回りや消耗戦になりやすいレースの新馬戦で台頭。"
    },
    "パイロ": {
        "base_rank": "A",
        "best_venues": ["大井", "川崎", "船橋"],
        "traits": "前向きな気性が新馬戦のスピードに直結。タフな大井コースへの親和性が極めて高い。"
    },
    "エスポワールシチー": {
        "base_rank": "A",
        "best_venues": ["船橋", "浦和", "高知", "園田"],
        "traits": "スピード持続力型。展開に左右されにくく、地方競馬場を問わず安定した先行力を発揮。"
    },
    "ダノンレジェンド": {
        "base_rank": "A",
        "best_venues": ["門別", "浦和", "川崎"],
        "traits": "短距離スプリントのスペシャリスト。門別のフレッシュチャレンジや浦和800m〜1400mで破壊力抜群。"
    },
    "マジェスティックウォリアー": {
        "base_rank": "A",
        "best_venues": ["船橋", "大井", "中京"],
        "traits": "大型のストライド型。船橋や大井外回りなど、外から長く脚を使える舞台の新馬戦で強い。"
    },
    "アジアエクスプレス": {
        "base_rank": "B",
        "best_venues": ["門別", "川崎", "中山"],
        "traits": "ダート短距離向きの筋骨隆々タイプ。初戦から前付けできるパワーがある。"
    },
    "ロードカナロア": {
        "base_rank": "B",
        "best_venues": ["大井", "船橋", "阪神"],
        "traits": "短距離の天性スピード。ダート新馬戦でも地力で押し切るが深い砂質には注意。"
    },
    "モーリス": {
        "base_rank": "B",
        "best_venues": ["川崎", "大井", "中山"],
        "traits": "パワー型でダートも走る。仕上がりはやや奥手傾向のため馬体重やパドック気配に注目。"
    }
}

BMS_PROFILES = {
    "サウスヴィグラス": {"rank": "S", "bonus": "短距離の出脚と前進気勢を劇的向上"},
    "シニスターミニスター": {"rank": "S", "bonus": "ダートでの粘りと馬力を底上げ"},
    "フレンチデピュティ": {"rank": "A", "bonus": "重・不良ダート時の推進力を大幅強化"},
    "シンボリクリスエス": {"rank": "A", "bonus": "大型馬になりやすくダート持久力を補強"},
    "キングカメハメハ": {"rank": "A", "bonus": "万能の先行センスとスピード持久力"},
    "クロフネ": {"rank": "A", "bonus": "ダートの王道。砂を被っても怯まない勝負根性"},
    "ゴールドアリュール": {"rank": "A", "bonus": "地方の深い砂を苦にしない純ダート適性"},
    "サンデーサイレンス": {"rank": "B", "bonus": "瞬発力と基礎スピードを付与"}
}

def analyze_bloodline_for_venue(sire: str, bms: str, venue: str = "大井") -> dict:
    sire = sire.strip() if sire else ""
    bms = bms.strip() if bms else ""
    venue = venue.strip() if venue else "大井"

    s_info = SIRE_PROFILES.get(sire, {
        "base_rank": "C",
        "best_venues": [],
        "traits": "地方ダート新馬戦のサンプル少数。個別の調教・仕上がり要確認。"
    })
    b_info = BMS_PROFILES.get(bms, {
        "rank": "B",
        "bonus": "標準的な血統適性"
    })

    venue_bonus = any(v in venue for v in s_info.get("best_venues", []))

    score_map = {"S": 4, "A": 3, "B": 2, "C": 1}
    score = score_map.get(s_info["base_rank"], 1) * 2 + score_map.get(b_info["rank"], 2)
    if venue_bonus:
        score += 2

    if score >= 11:
        overall = "S+ (当該場 新馬戦ベスト配合)"
    elif score >= 9:
        overall = "S (新馬戦激アツ)"
    elif score >= 7:
        overall = "A (高適性)"
    elif score >= 5:
        overall = "B (標準)"
    else:
        overall = "C (割引)"

    return {
        "venue": venue,
        "sire": sire,
        "sire_rank": s_info["base_rank"],
        "sire_traits": s_info["traits"],
        "best_venues": " / ".join(s_info.get("best_venues", ["特になし"])),
        "bms": bms,
        "bms_rank": b_info["rank"],
        "bms_bonus": b_info["bonus"],
        "overall_grade": overall,
        "venue_match": "◎ 舞台適合" if venue_bonus else "○ 通常"
    }
