#!/bin/bash
# アーカイブを再ビルドして GitHub Pages に公開する
set -e
cd "$(dirname "$0")"
python3 build.py
git add -A
if git diff --cached --quiet; then
  echo "変更なし"
else
  git commit -m "Update archive"
  git push
fi
