# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

md-patrol はローカルの Markdown 文書群に対する RAG 検索エージェント。新しく書いた文書が「過去の記載と似ていないか（類似検索）」「過去の記載と矛盾していないか（矛盾チェック）」を機械的にチェックする。埋め込みは Voyage、判定・採点は Claude（Anthropic API）。ベクトルストアは専用 DB を使わずローカル JSON（`resources/store/vector_store.json`）。

詳細は [docs/overview.md](docs/overview.md)（概要・要件）と [docs/architecture.md](docs/architecture.md)（全体構成）。各部品の詳細設計は `docs/design/` 配下（`rag-build.md` / `pipeline.md` / `agent.md` / `eval.md`）。

## Commands

依存は **Poetry** で管理（`pyproject.toml` / `poetry.lock`）。`package-mode = false`（アプリ扱い）なので自分のコードはパッケージとしてインストールせず、従来どおり `python -m src.xxx` で実行する。

```powershell
poetry install                                # 依存インストール（仮想環境を作成して導入）
poetry add <package>                          # 依存追加（pyproject.toml / poetry.lock 更新）
copy .env-example .env                        # API キー設定（VOYAGE_API_KEY / ANTHROPIC_API_KEY を記入）

poetry run python -m src.rag_build.rag_build  # ① RAG 構築（事前処理・1回）。target_mds/ → vector_store.json
poetry run python -m src.patrol.cli           # ② 実行（対話 CLI）
poetry run python -m src.eval.judge [YYYYMMDD] # ③ LLM 出力の自動採点（既定は当日分）
```

- 実行は `poetry run python -m ...`（パッケージ相対 import 前提なので、ファイル単体実行は不可）。
- テストフレームワーク・lint・ビルドツールは未導入。検証は上記コマンドの実行で行う。
- 文書を追加・変更したら `rag_build` を再実行してストアを作り直す（自動再構築・ファイル監視は無い）。

## アーキテクチャの要点

3 つの独立した機能パッケージが、共有層（`config` / `utils`）の上に乗る構造。

- **`src/patrol/`** — md-patrol エージェント本体。検索フェーズ。
- **`src/rag_build/`** — RAG 構築（チャンク化 → 埋め込み → ストア保存）。
- **`src/eval/`** — LLM 出力評価（LLM-as-judge による採点）。
- **`src/config/`** — 設定・定数の集約点（モデル名・パス・各種パラメータ・ログ出力先）。
- **`src/utils/`** — 共有基盤（トレースログ `create`、API クライアント `get_anthropic`/`get_voyage`、チャンク化器 `chunk_markdown_file`、プロンプト組立 `fill_template`）。

### パッケージ依存ルール（厳守）

`patrol` / `rag_build` / `eval` は**互いのソースを直接参照しない**。これら 3 つが自パッケージ外で参照してよいのは **`config` と `utils` のみ**。共有したいロジックは機能パッケージ間で参照させず `utils` に寄せる（例: チャンク化器は `utils/chunking.py`、プロンプトのテンプレ組立は `utils/prompt.py`）。`utils` 自身が外部参照してよいのは `config` のみ。このルールは [docs/architecture.md](docs/architecture.md) の「4. パッケージ依存ルール」にも記載。新しい共有コードを足すときは、機能パッケージ同士の import を増やさず utils 経由にすること。

### patrol の 2 戦略（同形インターフェース）

検索フェーズには 2 つの戦略があり、どちらも `(mode, query, exclude_file) -> {"results": [...]}` という**同じ呼び口**で `{"results": [...]}` を返す。`cli.py` が切り替えて呼ぶ。

- **固定パイプライン** ([patrol/pipeline.py](src/patrol/pipeline.py) の `analyze`): 1 回検索 → tool 強制で 1 回判定。
- **検索エージェント** ([patrol/agent.py](src/patrol/agent.py) の `run`): `search`/`expand`/`report_*` のツールループ。確信が持てるまで能動的に候補を集める。

両戦略は共通部品（`rag_search` のハイブリッド検索、`llm` の Claude 窓口、`prompts` のプロンプト組立、`pipeline.enrich` による id 逆引き補完）を共有する。LLM の回答は自由文ではなく tool スキーマに沿った構造化データ（候補 id ＋判定）で受け取り、id から元チャンクを逆引きして表示に補う。

ファイル単位入力（[patrol/file_input.py](src/patrol/file_input.py)）は、上記いずれの戦略も「入力を構築側と同じチャンク化で分割 → チャンクごとに戦略を直列実行 → ファイル単位レポートに集約」という形でラップする。

### LLM 呼び出しとトレース

- patrol の Claude 呼び出しは [patrol/llm/llm_client.py](src/patrol/llm/llm_client.py) の `run`/`complete` に集約。ここで入出力ペアを `eval_logger.log_pair` 経由で自動記録する。
- **eval（judge）は意図的に `llm_client`/`eval_logger` を経由せず** `utils.get_anthropic()` を直接叩く。採点呼び出し自体が次の採点対象に混ざるのを防ぐため。この分離は崩さないこと。

### ログ出力先（`logs/`）

`config.py` の定数で集約。書き込みコンポーネントごとに分離：

- `logs/trace/` (`TRACE_LOG_DIR`) — アプリ実行ログ（`.log` トレース。`utils.create` の出力）。
- `logs/patrol/llm_io_YYYYMMDD.jsonl` (`PATROL_LLM_LOG_DIR`) — patrol の LLM 入出力ペア（評価の素材）。
- `logs/judge/` (`JUDGE_LOG_DIR`) — judge の採点結果 `scored_*.jsonl` と LLM 入出力トレース `llm_io_*.jsonl`（usage 込み）。

judge は `logs/patrol/llm_io_*.jsonl` を読んで採点する。`logs/patrol/` と `logs/judge/` の `llm_io_*` は同形式（input/output ペア、usage は output 内）で、`component` をフォルダ名で区別する設計。

### チャンク化

`utils.chunk_markdown_file` が 1 ファイルを分割し、各チャンクに 2 種のテキストを持たせる：`content`（文脈ヘッダ＋本文、コード込み。表示・矛盾判定・BM25 用）と `embed_text`（コード除去。ベクトル化専用）。コードブロックの途中では絶対に分割しない。チャンク id は `content` の SHA-1 先頭 12 文字（内容が同じなら再構築をまたいでも同じ id）。
