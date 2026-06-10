"""
store_index.py — ベクトルストアの索引（expand 用・ロードの使い回し）

エージェントのループでは search/expand が何度も呼ばれる。そのたびに store を読み直すと
コストが効くため、records を 1 度だけロードしてキャッシュし、使い回す（agent.md 5.2）。

expand のためのファイル別索引も持つ。出現順は store の records 順をそのまま信頼する
（追加メタは持たない。agent.md 5.3）。RAG 構築が「ファイル名順 × ファイル内の見出し
出現順」で records に積むため、同じ file の records を records 順に並べれば前後関係になる。
"""

from .hybrid_search import load_store


class StoreIndex:
    """records を保持し、id 逆引きと expand（同一ファイルの前後取得）を提供する。"""

    def __init__(self, records: list):
        self.records = records
        self._by_id = {rec["id"]: rec for rec in records}

        # ファイルごとに「records 順（=出現順）」のリストを作る。値はそのファイル内の
        # records と、各 id のファイル内インデックスを引く辞書。
        self._file_order = {}      # file -> [rec, rec, ...]（出現順）
        self._pos_in_file = {}     # id -> そのファイル内での 0 始まり位置
        for rec in records:
            seq = self._file_order.setdefault(rec["file"], [])
            self._pos_in_file[rec["id"]] = len(seq)
            seq.append(rec)

    def get(self, rec_id: str):
        """id から record を返す（無ければ None）。"""
        return self._by_id.get(rec_id)

    def has(self, rec_id: str) -> bool:
        return rec_id in self._by_id

    def expand(self, rec_id: str, scope: str = "neighbors", neighbors: int = 2) -> list:
        """起点 id と同じファイルのチャンクを出現順で返す。

        scope="neighbors": 起点の前後 neighbors 件（起点含む）
        scope="same_file": 同ファイルの全チャンク
        起点 id が存在しなければ空リスト。
        """
        rec = self._by_id.get(rec_id)
        if rec is None:
            return []

        seq = self._file_order[rec["file"]]
        if scope == "same_file":
            return list(seq)

        pos = self._pos_in_file[rec_id]
        start = max(0, pos - neighbors)
        end = min(len(seq), pos + neighbors + 1)
        return seq[start:end]


# プロセス内で 1 度だけ作って使い回す（遅延初期化）
_index = None


def get_index() -> StoreIndex:
    """StoreIndex を取得する（無ければ store をロードして構築）。"""
    global _index
    if _index is None:
        _index = StoreIndex(load_store())
    return _index
