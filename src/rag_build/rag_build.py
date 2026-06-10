import os
import json
import time
import hashlib

from ..config import config  # 設定の集約点（モデル名・チャンク上限・パスなど）
from .. import utils  # Voyage クライアント・チャンク化器は utils に一元化


def _chunk_id(content: str) -> str:
    """チャンクの content から内容ハッシュの ID を作る（同じ内容なら毎回同じ ID）。"""
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]


def _embed_batch_with_retry(texts: list):
    """1 バッチを Voyage でベクトル化する。一時エラー時は指数バックオフでリトライ。"""
    last_error = None
    for attempt in range(1, config.EMBED_MAX_RETRIES + 1):
        try:
            result = utils.get_voyage().embed(texts, model=config.EMBEDDING_MODEL, input_type="document")
            return result.embeddings  # 入力と同じ順序で返る
        except Exception as e:
            last_error = e
            if attempt == config.EMBED_MAX_RETRIES:
                break
            wait = config.EMBED_RETRY_BASE_WAIT * (2 ** (attempt - 1))
            print(f"  埋め込み失敗（{attempt}/{config.EMBED_MAX_RETRIES}）: {e} → {wait:.0f}秒後に再試行")
            time.sleep(wait)
    raise RuntimeError(f"埋め込みに失敗（{config.EMBED_MAX_RETRIES}回リトライ後）: {last_error}")


def embed_texts(texts: list):
    """テキスト一覧をバッチに分けてベクトル化し、入力と同じ順序で連結して返す。"""
    vectors = []
    for start in range(0, len(texts), config.EMBED_BATCH_SIZE):
        batch = texts[start:start + config.EMBED_BATCH_SIZE]
        print(f"  ベクトル化中... {start + 1}〜{start + len(batch)} / {len(texts)} 件")
        vectors.extend(_embed_batch_with_retry(batch))
    return vectors


def main():
    """resources/target_mds/ を全件チャンク化 → ベクトル化 → JSON 一括保存（既存は上書き）。"""
    logger = utils.create("rag_build")
    logger.write("config", {
        k: v for k, v in vars(config).items()
        if k.isupper() and not k.startswith("_")
    })

    md_files = sorted(
        os.path.join(config.MDS_DIR, name)
        for name in os.listdir(config.MDS_DIR)
        if name.endswith(".md")
    )
    logger.write("対象Markdown", [os.path.basename(p) for p in md_files])

    all_chunks = []
    for path in md_files:
        file_chunks = utils.chunk_markdown_file(path)
        print(f"{os.path.basename(path)}: {len(file_chunks)} チャンク")
        logger.write("チャンク化", {"file": os.path.basename(path), "チャンク数": len(file_chunks)})
        all_chunks.extend(file_chunks)

    print(f"\n合計 {len(all_chunks)} チャンクをベクトル化します（model={config.EMBEDDING_MODEL}）...")
    logger.write("ベクトル化開始", {"合計チャンク数": len(all_chunks), "model": config.EMBEDDING_MODEL})

    # コードを除いた embed_text をベクトル化する
    vectors = embed_texts([c["embed_text"] for c in all_chunks])

    records = []
    for chunk, vector in zip(all_chunks, vectors):
        records.append({
            "id": _chunk_id(chunk["content"]),
            "content": chunk["content"],
            "embed_text": chunk["embed_text"],
            "file": chunk["file"],
            "heading_path": chunk["heading_path"],
            "embedding": vector,
        })

    os.makedirs(os.path.dirname(config.STORE_PATH), exist_ok=True)
    with open(config.STORE_PATH, "w", encoding="utf-8") as f:
        json.dump({"model": config.EMBEDDING_MODEL, "records": records}, f, ensure_ascii=False)

    print(f"\n保存しました: {config.STORE_PATH}")
    print(f"  チャンク数: {len(records)}")
    print(f"  ベクトル次元: {len(records[0]['embedding']) if records else 0}")
    logger.write("保存完了", {
        "store_path": config.STORE_PATH,
        "チャンク数": len(records),
        "ベクトル次元": len(records[0]["embedding"]) if records else 0,
    })


if __name__ == "__main__":
    main()
