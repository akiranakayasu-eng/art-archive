# SIGGRAPH Art Archive（Zotero / Notion 不要）

## 仕組み
- デスクトップ上の `Art Paperサムネイル/`（`2026sep/` のようなフォルダの中にあっても自動で見つけます）の中の年度フォルダ（例: `SIGGRAPH 2026 Art Papers`, `SIGGRAPH Asia 2025 Art Gallery`）をそのまま読みます。
- 各フォルダの `.bib`（Crossref生成）と `{タイトル}.jpg` を照合し、このフォルダの `docs/siggraph/` にサイトを書き出します（`update.sh` が `../ars-expanded-archive/docs/` を `docs/ars/` にコピーし、`docs/index.html` から `siggraph/` へ転送）。
- 必要なのは Mac に最初から入っている `python3` だけ。追加インストールなし。
- `docs/` を GitHub Pages で公開すれば無料のサイトになります。

## 毎年やること（これだけ）
1. 新しい年度フォルダを `Art Paperサムネイル/` に入れる（bib と jpg。今まで通り Claude に頼んでOK）
2. ターミナルで:
   ```
   cd ~/Dropbox/ClaudeWork/web/siggraph-art-archive && python3 build.py
   ```
   画像が見つからない論文があれば、ここで一覧表示されます。
3. 公開している場合は `docs/` を push（または Claude に「アーカイブ更新して」と頼む）

## デザインを変えたいとき（データには触れずに変えられます）
- `style.css`：色・フォント・余白・カードの大きさなど見た目のすべて
- `template.html`：ページの構成とカード1枚分のHTML（`<template id="card-tpl">` の中）。要素を並べ替えたり、`data-f="venue"`（掲載誌）を足したりできます
- `assets/`：ロゴや背景画像、フォントなど好きなファイルを置くと `docs/assets/` にコピーされます
- 変えたら `python3 build.py` で反映。Claude に「カードを大きく」「黒背景で」などと頼んでもOK

## フォルダ名のルール
`SIGGRAPH 2026 Art Papers` / `SIGGRAPH Asia 2025 Art Gallery` の形なら自動で年度・会議・種別に振り分けます。それ以外の名前のフォルダは無視します。
画像ファイル名は記号の違い（`:` → `-` など）を無視して照合します。

## 概要と日本語訳（data/ フォルダ）
- `data/legacy.json`：Notionから移した2020〜2025年分（概要・日本語訳つき）。サムネイルは `data/legacy-thumbs/` に置く
- `data/abstracts-YYYY.json`：その年の概要（CrossrefからDOIで取得）
- `data/translations-YYYY.json`：その年の日本語訳
- Art Gallery の作品には論文の概要（Abstract）がないため、概要と訳は Art Papers だけです。Art Gallery の作品を開くと、その旨の注記が出ます
- 新しい年は「YYYY年の概要と訳を作って」とClaudeに頼めば、この2つのファイルを作ります。カードをクリックすると概要と訳が表示されます

## 公開サイトの更新

公開サイトの更新は `./update.sh` を実行するだけ（ビルド → commit → push。GitHub Pages に数分で反映）。

公開URL: https://akiranakayasu-eng.github.io/siggraph-art-archive/
