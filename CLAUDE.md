# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

md-checker はローカルの Markdown 文書群に対する RAG 検索エージェント。詳細は [docs/overview.md](docs/overview.md)（概要・要件）と [docs/architecture.md](docs/architecture.md)（全体構成）。各部品の詳細設計は `docs/design/` 配下（`rag-build.md` / `agent.md` / `eval.md`）。

## Commands

```powershell
poetry install                                          # 依存インストール
copy .env-example .env                                  # API キー設定

poetry run python -m src.interface.build                # ① RAG 構築
poetry run python -m src.interface.checker              # ② 実行（対話 CLI）
poetry run python -m src.interface.judge [YYYYMMDD]     # ③ LLM 出力の自動採点
```

実行は `poetry run python -m ...`（パッケージ相対 import 前提）。文書を追加・変更したら ① を再実行。

## アーキテクチャの要点

軽量クリーンアーキテクチャ（`interface → usecase → domain / infra` の一方向依存）。`domain` は外部依存ゼロが原則。詳細は [docs/architecture.md](docs/architecture.md)。

### LLM 呼び出しとトレース

- checker の Claude 呼び出しは `infra/llm.py` の `run` に集約。`log_to_eval=True`（既定）のとき入出力を自動記録。
- **judge は `log_to_eval=False`** で呼ぶ。採点呼び出し自体が checker の評価対象ログに混入するのを防ぐための意図的分離。この分離は崩さないこと。
