# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

md-checker はローカルの Markdown 文書群に対する RAG 検索エージェント。新しく書いた文書が「過去の記載と似ていないか（類似検索）」「過去の記載と矛盾していないか（矛盾チェック）」を機械的にチェックする。埋め込みは Voyage、判定・採点は Claude（Anthropic API）。ベクトルストアは専用 DB を使わずローカル JSON（`resources/store/vector_store.json`）。

詳細は [docs/overview.md](docs/overview.md)（概要・要件）と [docs/architecture.md](docs/architecture.md)（全体構成）。各部品の詳細設計は `docs/design/` 配下（`rag-build.md` / `agent.md` / `eval.md`）。

## Commands

依存は **Poetry** で管理（`pyproject.toml` / `poetry.lock`）。`package-mode = false`（アプリ扱い）なので自分のコードはパッケージとしてインストールせず、従来どおり `python -m src.xxx` で実行する。

```powershell
poetry install                                # 依存インストール（仮想環境を作成して導入）
poetry add <package>                          # 依存追加（pyproject.toml / poetry.lock 更新）
copy .env-example .env                        # API キー設定（VOYAGE_API_KEY / ANTHROPIC_API_KEY を記入）

poetry run python -m src.interface.build           # ① RAG 構築（事前処理・1回）。target_mds/ → vector_store.json
poetry run python -m src.interface.checker        # ② 実行（対話 CLI）
poetry run python -m src.interface.judge [YYYYMMDD] # ③ LLM 出力の自動採点（既定は当日分）
```

- 実行は `poetry run python -m ...`（パッケージ相対 import 前提なので、ファイル単体実行は不可）。
- テストフレームワーク・lint・ビルドツールは未導入。検証は上記コマンドの実行で行う。
- 文書を追加・変更したら `rag_build` を再実行してストアを作り直す（自動再構築・ファイル監視は無い）。

## アーキテクチャの要点

軽量クリーンアーキテクチャ（interface → usecase → domain / infra の一方向依存）。

```
src/
├─ interface/   cli.py                      # ユーザー受付・結果表示
├─ usecase/     rag_build.py, agent.py,     # 処理フローの組み立て
│               judge.py
├─ domain/      chunking.py,                # 純粋ロジック（外部依存ゼロ）
│               retrieval/{bm25, cosine,
│                          hybrid, expand,
│                          enrich}.py
├─ infra/       embedder.py, llm.py,        # 外部API・永続化・テンプレート読込
│               store.py, prompt.py,
│               logger.py
└─ config/      config.py                   # 設定・定数の集約点
```

### 依存方向ルール（厳守）

`interface → usecase → domain / infra` の一方向のみ。`domain` は外部依存ゼロが原則（`config` 参照は可）。新しい共有ロジックを追加する場合は `domain` または `infra` に置き、`usecase` 同士・`interface` 同士の直接参照を増やさない。

### 検索エージェント

検索フェーズは [usecase/agent.py](src/usecase/agent.py) の `run` のみ。`search`/`expand`/`report_*` のツールループで、確信が持てるまで能動的に候補を集めてから判定を出す。戻り値は `(mode, query, exclude_file) -> {"results": [...]}` 形式。`cli.py` が直接呼ぶ。

### LLM 呼び出しとトレース

- checker の Claude 呼び出しは [infra/llm.py](src/infra/llm.py) の `run`/`complete` に集約。`log_to_eval=True`（既定）のとき入出力ペアを自動記録する。
- **judge は `log_to_eval=False`** で呼ぶ。採点呼び出し自体が checker の評価対象ログ（`llm_io.jsonl`）に混入するのを防ぐための意図的分離。この分離は崩さないこと。

### ログ出力先（`logs/`）

`config.py` の定数で集約。書き込みコンポーネントごとに分離：

- `logs/trace/` (`TRACE_LOG_DIR`) — アプリ実行ログ（`.log` トレース。`infra/logger.create` の出力）。
- `logs/checker/llm_io_YYYYMMDD.jsonl` (`CHECKER_LLM_LOG_DIR`) — checker の LLM 入出力ペア（評価の素材）。
- `logs/judge/` (`JUDGE_LOG_DIR`) — judge の採点結果 `scored_*.jsonl` と LLM 入出力トレース `llm_io_*.jsonl`。

### チャンク化

`domain/chunking.chunk_markdown_file` が 1 ファイルを分割し、各チャンクに 2 種のテキストを持たせる：`content`（文脈ヘッダ＋本文、コード込み）と `embed_text`（コード除去。ベクトル化専用）。コードブロックの途中では絶対に分割しない。チャンク id は `content` の SHA-1 先頭 12 文字。
