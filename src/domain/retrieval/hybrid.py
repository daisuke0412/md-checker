from ...config import config
from .bm25 import bm25_search
from .cosine import cosine_search


def hybrid_search(records, query: str, query_vec, k: int = config.CANDIDATE_K):
    """ベクトル検索と BM25 を RRF で統合し、上位 k 件を返す（純粋関数）。

    引数:
      records   : 検索対象の record リスト（除外済みのものを渡す）
      query     : クエリ文字列（BM25 に使う）
      query_vec : クエリの埋め込みベクトル（cosine 検索に使う）
      k         : 返す件数
    戻り値: [(rrf_score, record), ...] を高い順に k 件。
    """
    vec_results = cosine_search(query_vec, records)
    bm25_results = bm25_search(query, records)

    rrf_scores = {}
    rec_by_id = {}
    for results in (vec_results, bm25_results):
        for rank, (_score, rec) in enumerate(results, start=1):
            doc_id = rec["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (config.RRF_K + rank)
            rec_by_id[doc_id] = rec

    merged = [(score, rec_by_id[doc_id]) for doc_id, score in rrf_scores.items()]
    merged.sort(key=lambda pair: pair[0], reverse=True)
    return merged[:k]
