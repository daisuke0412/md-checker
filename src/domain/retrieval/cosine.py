from ...config import config


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


def cosine_search(query_vec, records, k: int = config.PER_INDEX_K):
    """query_vec に意味が近いチャンクをコサイン類似度の高い順に k 件返す。

    引数 query_vec はベクトル（埋め込み済み）。ベクトル化は infra/embedder.py が担う。
    戻り値 [(score, record), ...] は他の検索関数と同じ形。
    """
    scored = [(cosine_similarity(query_vec, rec["embedding"]), rec) for rec in records]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:k]
