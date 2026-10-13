#!/usr/bin/env python3
"""SIGGRAPH / SIGGRAPH Asia Art Papers & Art Gallery archive builder.

Usage:
    python3 build.py [DATA_DIR] [OUT_DIR]

DATA_DIR (default: the 'Art Paperサムネイル' folder found on the Desktop) contains one folder per year/category:
    SIGGRAPH 2026 Art Papers/
        SIGGRAPH_2026_Art_Papers.bib
        {title}.jpg ...
    SIGGRAPH Asia 2025 Art Gallery/
        ...
OUT_DIR (default: <this folder>/docs) receives index.html and thumbs/.
Only the Python standard library is used.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

FOLDER_RE = re.compile(r"^(SIGGRAPH(?: Asia)?) (\d{4}) (Art Papers|Art Gallery)$")

LATEX = {
    r"\&": "&", r"\%": "%", r"\_": "_", r"\$": "$", r"\#": "#",
    "--": "–", "~": " ",
}


def nfc(s):
    return unicodedata.normalize("NFC", s)


def key(s):
    """Loose title key: NFKC, lowercase, letters/digits only."""
    s = unicodedata.normalize("NFKC", s).lower()
    return "".join(ch for ch in s if ch.isalnum())


ACCENTS = {"'": "\u0301", "`": "\u0300", '"': "\u0308", "^": "\u0302",
           "~": "\u0303", "=": "\u0304", ".": "\u0307", "c": "\u0327", "v": "\u030c"}


def clean(v):
    v = v.replace("\n", " ")
    v = re.sub(r"\{?\\([\'`\"^~=.cv])\s*\{?(\w)\}?\}?",
               lambda m: unicodedata.normalize("NFC", m.group(2) + ACCENTS[m.group(1)]), v)
    for a, b in LATEX.items():
        v = v.replace(a, b)
    v = re.sub(r"\\[a-zA-Z]+\s*", "", v)  # drop remaining commands
    v = v.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", v).strip()


def parse_bib(text):
    """Minimal brace-aware BibTeX parser (enough for Crossref output)."""
    entries, i, n = [], 0, len(text)
    while True:
        i = text.find("@", i)
        if i < 0:
            break
        m = re.match(r"@(\w+)\s*\{\s*([^,\s]*)\s*,", text[i:])
        if not m:
            i += 1
            continue
        etype, citekey = m.group(1).lower(), m.group(2)
        i += m.end()
        fields = {}
        while i < n:
            m = re.match(r"\s*,?\s*(\}|([A-Za-z_\-]+)\s*=\s*)", text[i:])
            if not m:
                i += 1
                continue
            if m.group(1) == "}":
                i += m.end()
                break
            name = m.group(2).lower()
            i += m.end()
            if text[i] in "{\"":
                close = "}" if text[i] == "{" else "\""
                depth, j = 0, i
                while j < n:
                    c = text[j]
                    if c == "\\":
                        j += 2
                        continue
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if close == "}" and depth == 0:
                            break
                    elif c == "\"" and close == "\"" and depth == 0 and j > i:
                        break
                    j += 1
                fields[name] = text[i + 1:j]
                i = j + 1
            else:
                m = re.match(r"([^,}\s]+)", text[i:])
                fields[name] = m.group(1) if m else ""
                i += m.end() if m else 0
        entries.append({"type": etype, "key": citekey, **fields})
    return entries


def authors(raw):
    out = []
    for a in re.split(r"\s+and\s+", clean(raw)):
        a = a.strip()
        if "," in a:
            last, first = [p.strip() for p in a.split(",", 1)]
            a = f"{first} {last}".strip()
        if a:
            out.append(a)
    return out


THUMB_PX = 1000  # longest side of the copies in docs/thumbs


def put_thumb(src, out_dir, name):
    """Copy src to docs/thumbs/<name>.jpg, shrunk with macOS sips when available.

    Without sips the file is copied as is (keeping its extension). The copy is
    skipped when it is newer than src. Returns the path relative to out_dir.
    """
    sips = shutil.which("sips")
    rel = f"thumbs/{name}{'.jpg' if sips else src.suffix.lower()}"
    dst = out_dir / rel
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return rel
    if not sips:
        shutil.copy2(src, dst)
        return rel
    size = subprocess.run([sips, "-g", "pixelWidth", "-g", "pixelHeight", str(src)],
                          capture_output=True, text=True).stdout
    dims = [int(n) for n in re.findall(r"pixel(?:Width|Height):\s*(\d+)", size)]
    cmd = [sips, "-s", "format", "jpeg", "-s", "formatOptions", "80"]
    if not dims or max(dims) > THUMB_PX:
        cmd += ["-Z", str(THUMB_PX)]
    r = subprocess.run(cmd + [str(src), "--out", str(dst)], capture_output=True, text=True)
    if r.returncode != 0 or not dst.exists():
        print(f"!! sips failed, copying as is: {src.name}", file=sys.stderr)
        shutil.copy2(src, dst)
    return rel


def match_thumbs(entries, root):
    """Pair legacy entries with images under root -> {entry index: Path}.

    File names are often shortened titles ('Homogenized Planet Imagery.jpg'),
    carry _1/_2 suffixes, or change a trailing word, so besides exact keys we
    accept prefix and long-common-prefix matches within the same year and
    conference (taken from the image's folder name). A fuzzy match uses an
    image only once; the best-scoring pair wins.
    """
    groups = {}  # (folder, key) -> (n, path); keep the lowest _n
    for p in root.rglob("*"):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        m = re.match(r"(.*?)_(\d+)$", nfc(p.stem))
        stem, n = (m.group(1), int(m.group(2))) if m else (nfc(p.stem), 0)
        g = (nfc(p.parent.name), key(stem))
        if g not in groups or n < groups[g][0]:
            groups[g] = (n, p)
    pairs = []
    for (folder, k), (n, p) in groups.items():
        if not k:
            continue
        low = folder.lower()
        y = re.search(r"(?:19|20)\d\d", folder)
        cat = "Art Gallery" if "gallery" in low else "Art Papers" if "paper" in low else None
        for i, e in enumerate(entries):
            ek = key(e["t"])
            if k == ek or k == key(e.get("doi", "")):
                tier = 3
            elif y is None or int(y.group()) != e["y"] or ("asia" in low) != ("Asia" in e["c"]):
                continue
            elif ek.startswith(k) or k.startswith(ek):
                tier = 2
            else:
                lcp = len(os.path.commonprefix([k, ek]))
                if lcp < 20 or lcp < min(len(k), len(ek)) / 2:
                    continue
                tier = 1
            same = (y is not None and int(y.group()) == e["y"]) + (cat == e["k"])
            pairs.append(((tier, same, len(os.path.commonprefix([k, ek]))), i, (folder, k), p))
    pairs.sort(key=lambda x: x[0], reverse=True)
    out, used = {}, set()
    for (tier, *_), i, g, p in pairs:
        if i in out or (tier < 3 and g in used):
            continue
        out[i] = p
        used.add(g)
    return out


def add_extra_data(items, out_dir, report):
    """Merge this folder's data/*.json into items.

    data/legacy.json   : list of full entries for years without a bib folder
                         (imported from Notion); thumbnails in data/legacy-thumbs/
    data/<other>.json  : {DOI: "abstract"} or {DOI: {"abs":..., "ja":..., "tags":[...]}}
                         adds abstracts / Japanese translations to existing entries
    """
    data = Path(__file__).parent / "data"
    if not data.is_dir():
        return
    by_doi = {it["doi"].lower(): it for it in items if it["doi"]}
    legacy = data / "legacy.json"
    if legacy.exists():
        entries = [{"v": "", "img": "", **e}
                   for e in json.loads(legacy.read_text(encoding="utf-8"))
                   if e.get("doi", "").lower() not in by_doi]  # a bib folder for that year wins
        lt = data / "legacy-thumbs"
        imgs = match_thumbs(entries, lt) if lt.is_dir() else {}
        added = with_img = 0
        for i, e in enumerate(entries):
            img = imgs.get(i)
            if img:
                h = hashlib.sha1((e["doi"] or e["t"]).encode()).hexdigest()[:12]
                e["img"] = put_thumb(img, out_dir, h)
                with_img += 1
            items.append(e)
            if e["doi"]:
                by_doi[e["doi"].lower()] = e
            added += 1
        report.append(f"過去分（legacy.json）: {added}件 / 画像 {with_img}")
    for f in sorted(data.glob("*.json")):
        if f.name in ("legacy.json", "thumb-pos.json"):
            continue
        n = 0
        for doi, v in json.loads(f.read_text(encoding="utf-8")).items():
            it = by_doi.get(doi.lower().replace("https://doi.org/", ""))
            if not it:
                continue
            v = {"abs": v} if isinstance(v, str) else v
            for k in ("abs", "ja", "tags"):
                if v.get(k) and not it.get(k):
                    it[k] = v[k]
                    n += 1
        report.append(f"{f.name}: {n}項目を追加")


def build(data_dir, out_dir):
    thumbs = out_dir / "thumbs"
    thumbs.mkdir(parents=True, exist_ok=True)
    items, report = [], []
    for folder in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        m = FOLDER_RE.match(nfc(folder.name))
        if not m:
            continue
        conf, year, cat = m.group(1), int(m.group(2)), m.group(3)
        bibs = sorted(folder.glob("*.bib"))
        if not bibs:
            report.append(f"!! {folder.name}: .bib がありません")
            continue
        jpgs = {key(nfc(p.stem)): p for p in folder.iterdir()
                if p.suffix.lower() in (".jpg", ".jpeg", ".png")}
        used, n_entries, missing = set(), 0, []
        for bib in bibs:
            for e in parse_bib(bib.read_text(encoding="utf-8")):
                title = clean(e.get("title", ""))
                if not title or title.startswith("Proceedings of"):
                    continue
                n_entries += 1
                doi = clean(e.get("doi", ""))
                img = jpgs.get(key(title))
                thumb = ""
                if img:
                    used.add(key(title))
                    h = hashlib.sha1((doi or title).encode()).hexdigest()[:12]
                    thumb = put_thumb(img, out_dir, h)
                else:
                    missing.append(title)
                items.append({
                    "t": title,
                    "a": authors(e.get("author", "")),
                    "c": conf, "y": year, "k": cat,
                    "doi": doi,
                    "v": clean(e.get("journal", "") or e.get("booktitle", "")),
                    "img": thumb,
                })
        extra = [jpgs[k].name for k in jpgs if k not in used]
        line = f"{folder.name}: {n_entries}件 / 画像 {len(used)}"
        if missing:
            line += "\n   画像なし: " + "; ".join(missing)
        if extra:
            line += "\n   対応する論文がない画像: " + "; ".join(extra)
        report.append(line)
    add_extra_data(items, out_dir, report)
    # data/thumb-crops/<name>.jpg replaces docs/thumbs/<name>.jpg (e.g. the artwork cut out of a paper page)
    crops = Path(__file__).parent / "data" / "thumb-crops"
    if crops.is_dir():
        n = 0
        for p in crops.glob("*.jpg"):
            if (out_dir / "thumbs" / p.name).exists():
                shutil.copy2(p, out_dir / "thumbs" / p.name)
                n += 1
        report.append(f"トリミング画像（data/thumb-crops）: {n}枚")
    # data/thumb-pos.json: {"<name>.jpg": "50% 0%"} sets where a card crops that image (CSS object-position)
    pos_file = Path(__file__).parent / "data" / "thumb-pos.json"
    if pos_file.exists():
        pos = json.loads(pos_file.read_text(encoding="utf-8"))
        for it in items:
            if it.get("img") and Path(it["img"]).name in pos:
                it["pos"] = pos[Path(it["img"]).name]
    items.sort(key=lambda x: (-x["y"], x["c"], x["k"], x["t"].lower()))
    tpl = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    page = tpl.replace("/*DATA*/[]", json.dumps(items, ensure_ascii=False)
                       .replace("</", "<\\/"))
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("")
    here = Path(__file__).parent
    shutil.copy2(here / "style.css", out_dir / "style.css")
    if (here / "assets").is_dir():  # 好きな画像・フォントなどを置ける
        shutil.copytree(here / "assets", out_dir / "assets", dirs_exist_ok=True)
    print("\n".join(report))
    print(f"\n合計 {len(items)} 件 → {out_dir / 'index.html'}")


def find_data():
    """Find 'Art Paperサムネイル' on the Desktop, even inside a subfolder."""
    desk = Path.home() / "Desktop"
    hits = [p for pat in ("Art Paperサムネイル", "*/Art Paperサムネイル", "*/*/Art Paperサムネイル")
            for p in desk.glob(pat) if p.is_dir()]
    if not hits:  # macOS may store the name decomposed (NFD)
        hits = [p for p in desk.rglob("*") if p.is_dir() and nfc(p.name) == "Art Paperサムネイル"]
    if not hits:
        sys.exit("デスクトップに「Art Paperサムネイル」フォルダが見つかりません。"
                 "場所を指定してください: python3 build.py <フォルダ>")
    found = max(hits, key=lambda p: p.stat().st_mtime)
    print(f"データ: {found}\n")
    return found


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    data = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else find_data()
    out = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else here / "docs"
    build(data.resolve(), out.resolve())
