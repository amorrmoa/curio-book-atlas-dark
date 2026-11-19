# CURIO IDEA ATLAS — 初回公開用（190冊）

**これは差分更新用ではなく、GitHub Pages にまだ Curio Idea Atlas がない場合にも使える初回公開用です。** 既存の Curio Book Atlas 本体は変更しません。

## ZIPを展開してアップロードする
GitHub の `amorrmoa/curio-book-atlas-dark` の `main` に、以下のフォルダ構成を保持して追加します。**ZIPそのものを1ファイルとしてアップロードしないでください。**

- `docs/curio-idea-atlas.html` — 最初に開けるHTML（近似配置・190冊）
- `docs/curio-idea-atlas-data.json` — 初期概念データ
- `data/curio_idea_atlas_seed.xlsx` — 今回添付された190冊の書誌スナップショット
- `tools/build_curio_idea_map.py` — タイトル語抽出
- `tools/build_curio_semantic_map.py` — 意味ベクトル + UMAP
- `tools/curio-idea-atlas.template.html` — デザイン
- `tools/camel-book-sea.webp` — 駱駝画像
- `tools/semantic-requirements.txt` — 依存ライブラリ
- `.github/workflows/update-curio-idea-atlas.yml` — 自動更新設定

既存の同名ファイルがある場合は上書きしますが、**`docs/index.html`、既存の書誌用ワークフローは変更しません。**

## 初回公開
1. 上記のファイル群を `main` にコミットします。
2. `Actions` → `Update Curio Idea Atlas (semantic)` → `Run workflow` で再生成を実行します。
3. `semantic-map` ジョブが成功したことを確認します。
4. GitHub Pages が `main` の `docs/` を公開している場合、下記URLで地図が開きます。

`https://amorrmoa.github.io/curio-book-atlas-dark/curio-idea-atlas.html`

ZIP内のHTMLは **TF-IDFベースの近似配置** で、初回から表示可能です。多言語モデルとUMAPにより意味ベクトルに基づく配置へ置き換わるのは、Actionが成功した後です。Actions が失敗した場合は古いHTMLが残ります。

## 今後、190冊から増えた場合
**同梱した `data/curio_idea_atlas_seed.xlsx` は初回用の控えです。これだけでは今後の書籍追加は反映されません。**
書誌マスターExcelまたは公開用書誌JSONが同じリポジトリの中で増えていれば、スクリプトは収録冊数の多いものを優先して新しい地図を生成します。同数の場合は、実際に更新しているマスターをseedより優先します。

複数の書誌ファイルが同数で、どれが最新かわからない場合は安全のため生成を停止します。確実にするには `.github/workflows/update-curio-idea-atlas.yml` の Build コマンドへ `--input data/本当のマスター.xlsx` のように書誌ファイルを明示してください。実際の既存リポジトリのファイル構成は今回検証できていないので、この点は初回Actionで要確認です。

## 事前検証
添付の190冊Excelを入力にして、`--backend preview` でHTML再生成と冊数の整合性を確認済みです。多言語モデルのダウンロードとGitHub Pagesへの実公開は未検証です。
