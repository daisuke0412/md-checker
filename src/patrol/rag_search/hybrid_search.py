import json

from .cosine_similarity_search import cosine_similarity_search
from .bm25_search import bm25_search
from ...config import config


def load_store(path: str = config.STORE_PATH):
    """vector_store.json を読み込み records を返す。"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # ストアの埋め込みモデルが検索側と違うと意味空間がずれるため警告する
    store_model = data.get("model")
    if store_model and store_model != config.EMBEDDING_MODEL:
        print(
            f"[警告] ストアのモデル({store_model})と検索側({config.EMBEDDING_MODEL})が不一致。"
            f"rag_build.py で再構築してください。"
        )
    return data["records"]


def search(query: str, k: int = config.CANDIDATE_K, exclude_file: str = None):
    """ベクトル検索と BM25 を RRF で統合し、上位 k 件を返す。

    引数:
      exclude_file : 指定すると、その file を持つ record を検索前に除外する。
                     ファイル単位入力で構築済みファイルを入力したときの自己マッチ回避
                     （docs/design/pipeline.md 3・7.2）。None なら何も除外しない。
    戻り値: [(rrf_score, record), ...] を高い順に k 件。
    """
    # vector_store.json（RAG）から records を読み込む
    records = load_store()

    # 同名ファイルの除外（自己マッチ回避）。ベクトル・BM25 の両方が除外後の records を見る
    if exclude_file is not None:
        records = [rec for rec in records if rec["file"] != exclude_file]
        if not records:
            return []

    # 1. 各検索から順位つき結果をもらう（取り寄せ件数は各検索の既定 config.PER_INDEX_K）
    vec_results = cosine_similarity_search(query, records)
    bm_results = bm25_search(query, records)

    # 2. チャンクごとに RRF スコアを足し込む（同一判定は record の id、rank は 1 始まり）
    rrf_scores = {}
    rec_by_id = {}
    for results in (vec_results, bm_results):
        for rank, (_score, rec) in enumerate(results, start=1):
            doc_id = rec["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (config.RRF_K + rank)
            rec_by_id[doc_id] = rec

    # 3. RRF スコアの高い順に並べ、上位 k 件を返す
    merged = [(score, rec_by_id[doc_id]) for doc_id, score in rrf_scores.items()]
    merged.sort(key=lambda pair: pair[0], reverse=True)
    return merged[:k]
