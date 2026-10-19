#!/usr/bin/env python3
"""Art Archive の統計ページを作る（docs/stats/index.html）。

    python3 stats.py

読むもの:
  docs/siggraph/index.html, docs/ars/index.html に埋め込まれた作品データ（build.py / update.sh の出力）
  data/stats-official.json   主催者が公表した投稿数・採択数など（出典URLつき、手で更新）
書くもの:
  docs/stats/index.html      stats.html（テンプレート）にデータを埋め込んだもの

テーマの判定は概要（abstract）のキーワード一致です。THEMES の正規表現を変えれば判定が変わります。
Python 標準ライブラリだけで動きます。
"""
import collections
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE / "docs"

# テーマ: (ラベル 日本語, ラベル English, 正規表現)。大文字の略語は大文字小文字を区別して照合する。
THEMES = {
    "ai": ("AI・機械学習", "AI / machine learning",
           r"artificial intelligence|machine learning|machine-learning|neural network|deep learning|"
           r"generative model|diffusion model|large language model|language model|chatbot|"
           r"text-to-image|stable diffusion|midjourney|chatgpt",
           r"\bAI\b|\bGANs?\b|\bLLMs?\b|\bGPT|\bML\b"),
    "genai": ("生成AI", "Generative AI",
              r"generative ai|generative artificial|diffusion model|large language model|"
              r"text-to-image|text-to-video|stable diffusion|midjourney|chatgpt|dall.?e|gpt-?\d",
              r"\bLLMs?\b|\bGenAI\b"),
    "xr": ("VR・AR・XR", "VR / AR / XR",
           r"virtual reality|augmented reality|mixed reality|extended reality|head-mounted|immersive",
           r"\bVR\b|\bAR\b|\bXR\b|\bMR\b|\bHMD\b"),
    "robot": ("ロボット・機械", "Robotics",
              r"robot|kinetic sculpture|actuator|mechatron", None),
    "bio": ("バイオ・生命", "Bio / living systems",
            r"biolog|bioart|bio-art|living organism|organism|bacteri|microb|fung|mycel|cells?\b|dna\b|"
            r"artificial life|\balife\b", None),
    "eco": ("環境・気候", "Ecology / climate",
            r"climate|ecolog|anthropocene|environmental|sustainab|extinction|biodiversity|planetary", None),
    "data": ("データ・可視化", "Data / visualization",
             r"\bdata\b|dataset|visuali[sz]", None),
    "sound": ("音・音楽", "Sound / music",
              r"\bsound|music|audio|sonic|sonif", None),
    "body": ("身体・知覚", "Body / perception",
             r"\bbody\b|bodies|embodi|wearable|haptic|tactile|perception|choreograph|dance", None),
    "society": ("社会・政治", "Society / politics",
                r"colonial|politic|\bwar\b|migra|gender|feminis|identity|surveillance|democra|"
                r"inequal|justice|activis|indigenous", None),
}

# 2文字の国コード → 名前（Ars の作者表記 "(AT)" から拾うもの）
COUNTRY = {
    "AT": "Austria", "DE": "Germany", "US": "United States", "JP": "Japan", "NL": "Netherlands",
    "ES": "Spain", "CH": "Switzerland", "GB": "United Kingdom", "UK": "United Kingdom", "CO": "Colombia",
    "IT": "Italy", "SI": "Slovenia", "FR": "France", "TW": "Taiwan", "AR": "Argentina", "CN": "China",
    "CA": "Canada", "PL": "Poland", "KR": "South Korea", "BE": "Belgium", "BR": "Brazil", "MX": "Mexico",
    "AU": "Australia", "DK": "Denmark", "SE": "Sweden", "NO": "Norway", "FI": "Finland", "PT": "Portugal",
    "IE": "Ireland", "CZ": "Czechia", "HU": "Hungary", "RO": "Romania", "GR": "Greece", "TR": "Türkiye",
    "IL": "Israel", "IN": "India", "SG": "Singapore", "HK": "Hong Kong", "NZ": "New Zealand",
    "ZA": "South Africa", "NG": "Nigeria", "KE": "Kenya", "EG": "Egypt", "LB": "Lebanon", "IR": "Iran",
    "CL": "Chile", "PE": "Peru", "UA": "Ukraine", "RS": "Serbia", "HR": "Croatia", "SK": "Slovakia",
    "EE": "Estonia", "LT": "Lithuania", "LV": "Latvia", "LU": "Luxembourg", "IS": "Iceland",
    "TH": "Thailand", "PH": "Philippines", "ID": "Indonesia", "MY": "Malaysia", "VN": "Vietnam",
    "BG": "Bulgaria", "CY": "Cyprus", "MT": "Malta", "GH": "Ghana", "UG": "Uganda", "TN": "Tunisia",
    "MA": "Morocco", "PS": "Palestine", "PK": "Pakistan", "BD": "Bangladesh", "EC": "Ecuador",
    "UY": "Uruguay", "VE": "Venezuela", "CU": "Cuba", "GE": "Georgia", "AM": "Armenia", "BA": "Bosnia and Herzegovina",
    "MK": "North Macedonia", "AL": "Albania", "ZM": "Zambia", "ZW": "Zimbabwe", "RW": "Rwanda", "SN": "Senegal",
}
AWARD_ORDER = ["Golden Nica", "S+T+ARTS Grand Prize", "Grand Prize", "Award of Distinction",
               "Special Prize", "Young Creatives Prize", "Honorary Mention", "S+T+ARTS Honorary Mention",
               "S+T+ARTS Nomination", "Exhibited (no award)"]


def load_data(html_path):
    h = html_path.read_text(encoding="utf-8")
    m = re.search(r"(?:const|var|let)\s+DATA\s*=\s*(\[\{.*?\}\]);", h, re.S)
    return json.loads(m.group(1)) if m else []


def theme_hits(text):
    out = []
    for k, (_, _, ci, cs) in THEMES.items():
        if re.search(ci, text, re.I) or (cs and re.search(cs, text)):
            out.append(k)
    return out


def countries(authors):
    s = " ".join(authors)
    codes = set()
    for grp in re.findall(r"\(([A-Z]{2}(?:\s*[/,]\s*[A-Z]{2})*)\)", s):
        codes.update(re.findall(r"[A-Z]{2}", grp))
    return sorted(codes)


def n_people(s):
    """Ars の作者欄は "A (AT), B (DE)" のように1つの文字列に複数人が入るので人数に分ける。"""
    parts = re.split(r",\s*(?![^()]*\))|\s+&\s+|\s+and\s+", s)
    return max(1, len([p for p in parts if p.strip()]))


def series_key(x):
    if x["c"] in ("SIGGRAPH", "SIGGRAPH Asia"):
        return x["c"], x["k"]
    return x["c"], "Works" if x["c"] == "Ars Electronica" else "Papers"


def main():
    works = load_data(DOCS / "siggraph" / "index.html") + load_data(DOCS / "ars" / "index.html")
    rows = collections.defaultdict(lambda: {
        "n": 0, "nabs": 0, "authors": 0, "nauth": 0, "themes": collections.Counter(),
        "awards": collections.Counter(), "cats": collections.Counter(),
        "countries": collections.Counter(), "ncountry": 0,
    })
    for x in works:
        venue, prog = series_key(x)
        r = rows[(venue, prog, x["y"])]
        r["n"] += 1
        if x.get("a"):
            r["nauth"] += 1
            r["authors"] += sum(n_people(a) for a in x["a"])
        if x.get("abs"):
            r["nabs"] += 1
            r["themes"].update(theme_hits(x["t"] + ". " + x["abs"]))
        for a in x.get("r") or []:
            r["awards"][a] += 1
        for c in x.get("cat") or []:
            r["cats"][c] += 1
        cs = countries(x.get("a") or [])
        if cs:
            r["ncountry"] += 1
            r["countries"].update(cs)

    out = []
    for (venue, prog, year), r in sorted(rows.items()):
        out.append({
            "venue": venue, "prog": prog, "y": year, "n": r["n"], "nabs": r["nabs"],
            "authors": r["authors"], "nauth": r["nauth"], "themes": dict(r["themes"]), "awards": dict(r["awards"]),
            "cats": dict(r["cats"]), "countries": dict(r["countries"]), "ncountry": r["ncountry"],
        })

    official_path = HERE / "data" / "stats-official.json"
    official = json.loads(official_path.read_text(encoding="utf-8")) if official_path.exists() else {}

    payload = {
        "rows": out,
        "themes": {k: [v[0], v[1]] for k, v in THEMES.items()},
        "themeRules": {k: (v[2] + (" | " + v[3] if v[3] else "")) for k, v in THEMES.items()},
        "countryNames": COUNTRY,
        "awardOrder": AWARD_ORDER,
        "official": official,
    }
    tpl = (HERE / "stats.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    dest = DOCS / "stats"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "index.html").write_text(html, encoding="utf-8")
    print(f"stats: {len(works)} works → docs/stats/index.html")


if __name__ == "__main__":
    main()
