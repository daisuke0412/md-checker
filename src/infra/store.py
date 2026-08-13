import json

from ..config import config


class VectorStore:
    """records を保持し、id 逆引きと expand（同一ファイルの前後取得）を提供する。

    RAG 構築が「ファイル名順 × ファイル内の見出し出現順」で records に積むため、
    同じ file の records を records 順に並べれば前後関係になる。
    """

    def __init__(self, records: list):
        self.records = records
        self._by_id = {rec["id"]: rec for rec in records}

        self._file_order = {}   # file -> [rec, ...]（出現順）
        self._pos_in_file = {}  # id -> そのファイル内での 0 始まり位置
        for rec in records:
            seq = self._file_order.setdefault(rec["file"], [])
            self._pos_in_file[rec["id"]] = len(seq)
            seq.append(rec)

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


def load_records(path: str = config.STORE_PATH) -> list:
    """vector_store.json を読み込み records を返す。"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    store_model = data.get("model")
    if store_model and store_model != config.EMBEDDING_MODEL:
        print(
            f"[警告] ストアのモデル({store_model})と検索側({config.EMBEDDING_MODEL})が不一致。"
            f"rag_build.py で再構築してください。"
        )
    return data["records"]


# プロセス内で 1 度だけ作って使い回す（遅延初期化）
_index = None


def get_store() -> VectorStore:
    """VectorStore を取得する（無ければ store をロードして構築）。"""
    global _index
    if _index is None:
        _index = VectorStore(load_records())
    return _index
