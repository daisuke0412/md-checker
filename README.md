# md-patrol

ローカルの Markdown 文書群を対象に、**似た記載を見つけたり、過去の記載との矛盾を指摘したりする RAG 検索エージェント**です。技術ブログや社内文書を書くとき、「前にも似た説明を書いていないか」「過去の記載と食い違っていないか」を機械的にチェックします。

- **① 類似記載の検索** — 意味（ベクトル）＋語彙（BM25）のハイブリッド検索で、似た記載を探す
- **② 矛盾チェック** — 取得した候補と入力の主張を Claude に突き合わせさせ、矛盾を指摘する

入力はテキスト単位（文章を直接入力）でもファイル単位（Markdown 1 本まるごと）でも実行でき、判定は「固定パイプライン（1 回検索→1 回判定）」「検索エージェント（必要に応じ追加検索しながら判定）」の 2 戦略から選べます。

## セットアップ

```powershell
# 1. 依存パッケージのインストール（pyproject.toml から解決して仮想環境に導入）
poetry install

# 2. API キーの設定（.env-example をコピーして埋める）
copy .env-example .env
# .env に VOYAGE_API_KEY（埋め込み）と ANTHROPIC_API_KEY（判定）を記入
```

依存を追加するときは `poetry add <パッケージ>` を使う（`pyproject.toml` と `poetry.lock` が更新される）。

## 使い方

各コマンドは `poetry run` を付けて仮想環境内で実行する。

```powershell
# 1. RAG 構築（事前処理・1 回）
#    resources/target_mds/ の .md を読み、resources/store/vector_store.json を生成
poetry run python -m src.rag_build.rag_build

# 2. md-patrol の実行（対話 CLI）
#    機能（類似/矛盾）→ 戦略（固定/エージェント）→ 入力単位（テキスト/ファイル）を選んで実行
poetry run python -m src.patrol.cli

# 3. （任意）LLM 出力の自動採点（LLM-as-judge）
#    logs/patrol/ の LLM 入出力トレースを Claude に採点させる
poetry run python -m src.eval.judge
```

文書を追加・変更したら、RAG 構築（手順 1）を再実行してストアを作り直します。

## ドキュメント

- [docs/overview.md](docs/overview.md) — 概要・要件（最初に読む 1 枚）
- [docs/architecture.md](docs/architecture.md) — 全体構成・技術スタック・ディレクトリ構成
- 詳細設計
  - [docs/design/rag-build.md](docs/design/rag-build.md) — RAG 構築（チャンク化→埋め込み→ストア保存）
  - [docs/design/pipeline.md](docs/design/pipeline.md) — 固定パイプライン
  - [docs/design/agent.md](docs/design/agent.md) — 検索エージェント（ツールループ）
  - [docs/design/eval.md](docs/design/eval.md) — LLM 出力評価（採点）
- [docs/reference/](docs/reference/) — 参考資料（[rag-basics.md](docs/reference/rag-basics.md) など）

## 技術スタック

埋め込み: Voyage（`voyage-4-lite`）／ 判定・採点: Claude（Anthropic API, `claude-sonnet-4-6`）／ ベクトルストア: ローカル JSON ／ 語彙検索: 自前 BM25 ／ 統合: 自前 RRF ／ 言語: Python
