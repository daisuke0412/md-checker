import os

from ..config import config
from .. import utils  # 入力チャンク化は共有層のチャンク化器を使う（utils.chunk_markdown_file）


def analyze_file(strategy, mode: config.Mode, path: str) -> dict:
    """Markdown ファイル 1 本を分析し、ファイル単位のレポート(dict)を返す。

    引数:
      strategy : (mode, query, exclude_file) -> {"results": [...]} の呼び口。
                 pipeline.analyze または agent.run を渡す。
      mode     : config.Mode.SIMILARITY / CONTRADICTION
      path     : 入力 Markdown ファイルのパス
    戻り値:
      {
        "file": "<basename>",
        "summary": {"chunks": N, "hit_chunks": M, "results": 件数合計},
        "by_chunk": [{"input_heading": [...], "results": [...]}, ...],
      }
      by_chunk には結果のあった入力チャンクだけを残す。
    """
    file_name = os.path.basename(path)
    logger = utils.create(f"file_{mode.value}")
    logger.write("モード", mode.value)
    logger.write("入力ファイル", file_name)

    # 1. 入力チャンク化（構築側と同じ粒度。docs/design/pipeline.md 7.1）
    chunks = utils.chunk_markdown_file(path)
    logger.write("入力チャンク化", {"file": file_name, "チャンク数": len(chunks)})

    by_chunk = []
    total_results = 0
    for i, chunk in enumerate(chunks, start=1):
        # 2. チャンクごとに戦略を 1 本ずつ実行。自己マッチ回避のため同名ファイルを除外
        result = strategy(mode, chunk["content"], exclude_file=file_name)
        results = result["results"]
        logger.write("チャンク実行", {
            "index": i,
            "heading_path": chunk["heading_path"],
            "結果件数": len(results),
        })
        if results:
            by_chunk.append({
                "input_heading": chunk["heading_path"],
                "results": results,
            })
            total_results += len(results)

    # 3. 集約（入力チャンク軸のレポート）
    report = {
        "file": file_name,
        "summary": {
            "chunks": len(chunks),
            "hit_chunks": len(by_chunk),
            "results": total_results,
        },
        "by_chunk": by_chunk,
    }
    logger.write("最終レポート", report["summary"])
    return report
