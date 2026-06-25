import json

from ..config import config
from ..domain.retrieval.expand import StoreIndex


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


def get_index() -> StoreIndex:
    """StoreIndex を取得する（無ければ store をロードして構築）。"""
    global _index
    if _index is None:
        _index = StoreIndex(load_records())
    return _index
