import re
import math
from collections import Counter

from ...config import config  # 設定の集約点（BM25 のチューニング定数）


def tokenize(text: str):
    """テキストを単語に分割する（小文字化し、英数識別子はそのまま、日本語は 2-gram）。"""
    text = text.lower()
    tokens = []

    # 英数字・ハイフン・アンダースコアの連なり（例: voyage-3.5-lite）を 1 単語として抜き出す
    for match in re.findall(r"[a-z0-9_\-]+", text):
        tokens.append(match)

    # 英数字以外（日本語など）の連なりを 2-gram にする
    for chunk in re.findall(r"[^a-z0-9_\-\s]+", text):
        if len(chunk) == 1:
            tokens.append(chunk)
        else:
            for i in range(len(chunk) - 1):
                tokens.append(chunk[i:i + 2])

    return tokens


def build_index(records):
    """records から BM25 索引（スコア計算用の前計算値）を組み立てる。

    doc_tokens（各チャンクの単語出現回数）, doc_len（単語数）, avgdl（平均単語数）,
    df（各単語を含むチャンク数）, N（チャンク総数）。
    """
    doc_tokens = []
    doc_len = []
    df = Counter()  # 単語 -> その単語を含むチャンク数

    for rec in records:
        tokens = tokenize(rec["content"])
        counts = Counter(tokens)
        doc_tokens.append(counts)
        doc_len.append(len(tokens))
        for term in counts.keys():  # 出現回数ではなく「含むか」を 1 だけ足す
            df[term] += 1

    N = len(records)
    avgdl = (sum(doc_len) / N) if N else 0.0

    return {
        "records": records,
        "doc_tokens": doc_tokens,
        "doc_len": doc_len,
        "avgdl": avgdl,
        "df": df,
        "N": N,
    }


def _idf(term: str, index) -> float:
    """単語の IDF（希少さ）を返す: log(1 + (N - df + 0.5) / (df + 0.5))。"""
    df = index["df"].get(term, 0)
    N = index["N"]
    return math.log(1 + (N - df + 0.5) / (df + 0.5))


def bm25_search(query: str, records, k: int = config.PER_INDEX_K):
    """クエリに語彙が一致するチャンクを BM25 スコアの高い順に k 件返す。

    戻り値 [(score, record), ...] は他の検索関数と同じ形。
    """
    index = build_index(records)
    query_terms = tokenize(query)

    scored = []
    for i, rec in enumerate(index["records"]):
        counts = index["doc_tokens"][i]
        dl = index["doc_len"][i]
        score = 0.0
        for term in query_terms:
            tf = counts.get(term, 0)
            if tf == 0:
                continue  # このチャンクに無い単語は加点なし
            idf = _idf(term, index)
            # TF を飽和させ、長いチャンクを割り引く BM25 本体式
            denom = tf + config.BM25_K1 * (1 - config.BM25_B + config.BM25_B * (dl / index["avgdl"]))
            score += idf * (tf * (config.BM25_K1 + 1) / denom)
        scored.append((score, rec))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:k]
