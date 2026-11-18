# 奇想洋書航路 — チェコ前衛ダーク版（完全公開セット）

濃紺・墨黒を背景に、ミント、薄紅、ラベンダー、淡い金色をアクセントとして使ったチェコ前衛風の書誌サイト。**181冊、14テーマ、ISBN情報、月別表示、主テーマ別幾何学模様、右上CSV抽出**を収録しています。

## このZIPは「完全版」です

次のファイルをすべて含んでいます（差分パッチではありません）。

```text
.github/workflows/publish-manual-catalog.yml   # Excel更新・GitHub Pages公開
 data/curio_catalog.xlsx                       # 編集する書籍リスト（原本）
 docs/index.html                               # サイト本体
 docs/.nojekyll                                # Pages用
 docs/data/books.json                          # 公開用の書誌データ
 docs/data/catalog.js                          # ページ読み込みデータ
 docs/data/themes.json                         # 14テーマ
 tools/build_catalog.py                        # Excel → JSON / JS に変換
 tests/                                        # データの整合性テスト
 README.md                                     # この説明
 テーマ分類一覧.md                               # 主テーマ表
```

## GitHubへ最初からアップロードする（推奨）

1. GitHubの「New repository」から空の公開リポジトリを作ります。既存サイトを残したい場合、別名（例：`curio-book-atlas-dark`）で作ると安全です。**READMEや.gitignore等は作成時に自動追加しなくて大丈夫です。**
2. このZIPをパソコン上で展開します。ZIP自体を上げるのではなく、**展開した中身**（`.github`、`data`、`docs`、`tools`、`tests`、README.md など）をリポジトリの**一番上の階層**へ入れます。`.github` は隠しフォルダなので、Windowsで見えなければ「隠しファイル」を表示してください。
3. リポジトリの「Add file → Upload files」でファイルを追加して「Commit changes」を押します。**GitHubのWebアップロードでは、空フォルダは登録されないことがありますが問題ありません。**
4. 「Settings → Pages → Build and deployment → Source」を **GitHub Actions** にします（Branchではありません）。
5. 「Actions → Publish manually curated Curio Book Atlas → Run workflow」で初回実行（またはmainへのpush時に自動実行）。緑色になったら公開URLを確認します。
6. 既存の `amorrmoa/curio-book-atlas` を使う場合、以前の `update-and-deploy.yml` / `official-publishers.yml` 等の古い更新ワークフローは停止・削除し、今回の公開ワークフローだけにしてください（競合防止）。**これらの旧ファイルはZIPには入っていません**。古いファイルを勝手に消すことはありません。

## 以後の更新

`data/curio_catalog.xlsx` を編集し、同じパスへ上書きしてください。GitHub ActionsがExcelの整合性テスト、公開用データへの変換、サイト再公開を行います。

### CSVについて

サイト右上の「CSV抽出」は現在の絞り込み結果をダウンロードします。Excelで読みやすいUTF-8（BOM付き）です。**CSVをアップロードしてもサイトは更新されません**。更新元は `data/curio_catalog.xlsx` です。

### 補足

- 初期登録の181冊のうちISBNを確認・収録したのは121冊で、未確認は空欄です。番号を自動生成しません。
- 書影未登録の部分は各書籍の**主テーマ**に対応した抽象幾何学模様です。実際の表紙画像を偽装しません。
- 外部APIの常時巡回や自動新刊発見はありません。書誌リストの追加・修正はExcelで行います。
- オフラインで素早く確認したい場合は、別添の単体HTMLプレビューを開けます。公開用ファイルは `docs/index.html` です。
