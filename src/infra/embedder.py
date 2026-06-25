import os
import time

from dotenv import load_dotenv
import voyageai

from ..config import config

_voyage_client = None
_env_loaded = False


def _load_env_once() -> None:
    global _env_loaded
    if not _env_loaded:
        load_dotenv(config.ENV_PATH)
        _env_loaded = True


def _get_voyage() -> "voyageai.Client":
    global _voyage_client
    if _voyage_client is None:
        _load_env_once()
        _voyage_client = voyageai.Client(api_key=os.environ.get("VOYAGE_API_KEY"))
    return _voyage_client


def embed_query(query: str) -> list:
    """クエリを 1 つベクトル化する（input_type="query"）。"""
    result = _get_voyage().embed([query], model=config.EMBEDDING_MODEL, input_type="query")
    return result.embeddings[0]


def embed_documents(texts: list) -> list:
    """テキスト一覧をバッチに分けてベクトル化し、入力と同じ順序で連結して返す。

    一時エラー時は指数バックオフでリトライする（rag_build 用）。
    """
    vectors = []
    for start in range(0, len(texts), config.EMBED_BATCH_SIZE):
        batch = texts[start:start + config.EMBED_BATCH_SIZE]
        print(f"  ベクトル化中... {start + 1}〜{start + len(batch)} / {len(texts)} 件")
        vectors.extend(_embed_batch_with_retry(batch))
    return vectors


def _embed_batch_with_retry(texts: list) -> list:
    last_error = None
    for attempt in range(1, config.EMBED_MAX_RETRIES + 1):
        try:
            result = _get_voyage().embed(texts, model=config.EMBEDDING_MODEL, input_type="document")
            return result.embeddings
        except Exception as e:
            last_error = e
            if attempt == config.EMBED_MAX_RETRIES:
                break
            wait = config.EMBED_RETRY_BASE_WAIT * (2 ** (attempt - 1))
            print(f"  埋め込み失敗（{attempt}/{config.EMBED_MAX_RETRIES}）: {e} → {wait:.0f}秒後に再試行")
            time.sleep(wait)
    raise RuntimeError(f"埋め込みに失敗（{config.EMBED_MAX_RETRIES}回リトライ後）: {last_error}")
