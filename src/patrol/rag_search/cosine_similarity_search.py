from ...config import config
from ... import utils  # Voyage クライアントは utils に一元化（utils.get_voyage）


def embed_query(query: str):
    """クエリを 1 つベクトル化する（チャンクと同じモデル・input_type="query"）。"""
    result = utils.get_voyage().embed([query], model=config.EMBEDDING_MODEL, input_type="query")
    return result.embeddings[0]


def cosine_similarity(a, b) -> float:
    """2 ベクトルのコサイン類似度（-1〜1、1 に近いほど類似）を返す。"""
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / ((norm_a ** 0.5) * (norm_b ** 0.5))


def cosine_similarity_search(query: str, records, k: int = config.PER_INDEX_K):
    """クエリに意味が近いチャンクをコサイン類似度の高い順に k 件返す。

    戻り値 [(score, record), ...] は他の検索関数と同じ形。
    """
    query_vec = embed_query(query)

    scored = [(cosine_similarity(query_vec, rec["embedding"]), rec) for rec in records]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:k]
