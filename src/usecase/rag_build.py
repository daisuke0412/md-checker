import os
import json
import hashlib

from ..config import config
from ..domain.chunking import chunk_markdown_file
from ..infra.embedder import embed_documents
from ..infra.logger import create


def _chunk_id(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]


def main():
    """resources/target_mds/ を全件チャンク化 → ベクトル化 → JSON 一括保存（既存は上書き）。"""
    logger = create("rag_build")
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
        file_chunks = chunk_markdown_file(path)
        print(f"{os.path.basename(path)}: {len(file_chunks)} チャンク")
        logger.write("チャンク化", {"file": os.path.basename(path), "チャンク数": len(file_chunks)})
        all_chunks.extend(file_chunks)

    print(f"\n合計 {len(all_chunks)} チャンクをベクトル化します（model={config.EMBEDDING_MODEL}）...")
    logger.write("ベクトル化開始", {"合計チャンク数": len(all_chunks), "model": config.EMBEDDING_MODEL})

    vectors = embed_documents([c["embed_text"] for c in all_chunks])

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
