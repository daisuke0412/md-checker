"""
clients.py — 外部 API クライアントの一元管理

Anthropic（Claude）と Voyage（埋め込み）のクライアント生成を 1 か所に集約する。
各機能（llm / eval / rag_build / rag_search）は自前で生成せず、ここから取得する。

クライアントは初回利用時に 1 度だけ生成し、以降は使い回す（遅延初期化＋プロセス内キャッシュ）。
.env（API キー）の読み込みもここで 1 回だけ行う。
"""

import os

from dotenv import load_dotenv
import anthropic
import voyageai

from ..config import config

_anthropic_client = None
_voyage_client = None
_env_loaded = False


def _load_env_once() -> None:
    """.env を 1 度だけ読み込む（複数クライアントで重複読み込みしない）。"""
    global _env_loaded
    if not _env_loaded:
        load_dotenv(config.ENV_PATH)
        _env_loaded = True


def get_anthropic() -> "anthropic.Anthropic":
    """Anthropic（Claude）クライアントを取得する（無ければ生成して使い回す）。"""
    global _anthropic_client
    if _anthropic_client is None:
        _load_env_once()
        _anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _anthropic_client


def get_voyage() -> "voyageai.Client":
    """Voyage（埋め込み）クライアントを取得する（無ければ生成して使い回す）。"""
    global _voyage_client
    if _voyage_client is None:
        _load_env_once()
        _voyage_client = voyageai.Client(api_key=os.environ.get("VOYAGE_API_KEY"))
    return _voyage_client
