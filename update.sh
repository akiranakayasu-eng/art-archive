#!/bin/bash
# アーカイブを再ビルドして GitHub Pages に公開する
#   docs/siggraph/ : このフォルダの build.py で生成
#   docs/ars/      : ../ars-expanded-archive/docs/ をコピー（あれば）
#   docs/stats/    : stats.py で生成（統計ページ）
#   docs/index.html: siggraph/ へ転送するトップページ
set -e
cd "$(dirname "$0")"
python3 build.py
if [ -d ../ars-expanded-archive/docs ]; then
  mkdir -p docs/ars
  rsync -a --delete ../ars-expanded-archive/docs/ docs/ars/
  cat tabs.css >> docs/ars/style.css  # same top tabs on both pages
  # add the Statistics tab to the Ars page (its source lives in ../ars-expanded-archive)
  python3 - <<'PY'
from pathlib import Path
p = Path("docs/ars/index.html"); s = p.read_text(encoding="utf-8")
a = '<a class="tab" href="./" aria-current="page">Ars Electronica / Expanded</a>'
if "../stats/" not in s and a in s:
    p.write_text(s.replace(a, a + '<a class="tab" href="../stats/">Statistics</a>', 1), encoding="utf-8")
PY
fi
python3 stats.py  # docs/stats/: statistics from the two pages above + data/stats-official.json
cat > docs/index.html <<'HTML'
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=siggraph/">
<title>Art Archive</title></head>
<body><p><a href="siggraph/">SIGGRAPH Art Archive</a> · <a href="ars/">Ars Electronica / Expanded</a></p></body></html>
HTML
touch docs/.nojekyll
git add -A
if git diff --cached --quiet; then
  echo "変更なし"
else
  git commit -m "Update archive"
  git push
fi
