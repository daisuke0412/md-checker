import os
from enum import Enum


# --- 機能モード -------------------------------------------------------------
class Mode(str, Enum):
    """md-patrol の機能。類似検索と矛盾チェックの 2 つだけを許す。

    str を継承しているので、値（"similarity" / "contradiction"）を文字列として
    そのまま辞書キー・表示に使える。analyze() などはこの Enum を受け取ることで、
    タイプミスや未知の文字列を弾ける。
    """
    # 類似記載の検索（機能①）
    SIMILARITY = "similarity"
    # 矛盾チェック（機能②）
    CONTRADICTION = "contradiction"


# --- パス -------------------------------------------------------------------
# このファイルは src/config/ にある。2 つ上がプロジェクト直下。
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_RESOURCES = os.path.join(_ROOT, "resources")

# API キーの読み込み元
ENV_PATH = os.path.join(_ROOT, ".env")
# 構築フェーズの入力 Markdown 群
MDS_DIR = os.path.join(_RESOURCES, "target_mds")
# ベクトルストア
STORE_PATH = os.path.join(_RESOURCES, "store", "vector_store.json")
# プロンプト txt 置き場
PROMPTS_DIR = os.path.join(_RESOURCES, "prompts")
# 類似検索（機能①）
SIMILARITY_PROMPT_PATH = os.path.join(PROMPTS_DIR, "similarity.txt")
# 矛盾チェック（機能②）
CONTRADICTION_PROMPT_PATH = os.path.join(PROMPTS_DIR, "contradiction.txt")
# LLM-as-judge の採点プロンプト
JUDGE_PROMPT_PATH = os.path.join(PROMPTS_DIR, "judge.txt")
# エージェント（ツールループ）用のシステムプロンプト（行動指針＋判定基準）
AGENT_SIMILARITY_PROMPT_PATH = os.path.join(PROMPTS_DIR, "agent_similarity.txt")
AGENT_CONTRADICTION_PROMPT_PATH = os.path.join(PROMPTS_DIR, "agent_contradiction.txt")
# ログ出力のルート（成果物なので直下）
LOG_DIR = os.path.join(_ROOT, "logs")
# アプリ実行ログ（.log トレース）
TRACE_LOG_DIR = os.path.join(LOG_DIR, "trace")
# patrol の LLM 入出力トレース（llm_io_*.jsonl）
PATROL_LLM_LOG_DIR = os.path.join(LOG_DIR, "patrol")
# 評価（judge）: 採点結果 scored_* と LLM 入出力 llm_io_*
JUDGE_LOG_DIR = os.path.join(LOG_DIR, "judge")

# --- 埋め込み（Voyage）------------------------------------------------------
# 構築側・検索側で必ず同じモデルを使う（意味空間を揃えるため）。ストアの "model" にも記録。
EMBEDDING_MODEL = "voyage-4-lite"

# --- 構築フェーズ（チャンク化・埋め込み）-----------------------------------
# これ超のセクションのみ二次分割（rag-build.md 5.2）
CHUNK_MAX_TOKENS = 1200
# 1 リクエストに送るチャンク数の上限
EMBED_BATCH_SIZE = 128
# 一時エラー・レート制限時のリトライ回数
EMBED_MAX_RETRIES = 5
# 秒。リトライごとに指数的に伸ばす（2,4,8,...）
EMBED_RETRY_BASE_WAIT = 2.0

# --- 検索フェーズ（BM25 / RRF / 候補件数）----------------------------------
# BM25 のチューニング定数（標準的な既定値）
# TF（出現頻度）の飽和の強さ。1.2〜2.0 が定番
BM25_K1 = 1.5
# 長さ正規化の強さ。0=なし、1=最大。0.75 が定番
BM25_B = 0.75

# RRF の定数。小さくすると上位の差が際立つ。60 が定番
RRF_K = 60
# 融合前に各検索から取り寄せる候補数（最終 k より大きめ）
PER_INDEX_K = 8
# 最終的に LLM へ渡す候補数（取捨選択は Claude に任せ多めに集める）
CANDIDATE_K = 5

# 入力テキストの最大文字数。1 チャンク上限（トークン）に「1トークン≒1文字」で揃える。
# これを超える入力は受け付けない（pipeline.py の対話エントリで検査）。
MAX_INPUT_CHARS = CHUNK_MAX_TOKENS  # = 1200

# --- LLM（Claude / Anthropic）----------------------------------------------
# 判定に使うモデル
CLAUDE_MODEL = "claude-sonnet-4-6"
# 出力トークン上限
CLAUDE_MAX_TOKENS = 2000

# --- エージェント（ツールループ。agent.md 8）-------------------------------
# LLM 呼び出しの上限。到達したら report_* を強制して必ず結果を出す
MAX_AGENT_TURNS = 5
# search/expand の累計呼び出し上限
MAX_TOOL_CALLS = 6
# 1 回の search で返す候補数
AGENT_SEARCH_K = 5
# expand の neighbors で取る前後チャンク数（前後それぞれ）
EXPAND_NEIGHBORS = 2
