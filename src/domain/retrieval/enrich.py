def enrich(judged_results, rec_by_id) -> list:
    """LLM の判定（id＋reason 等）に、id で逆引きした元チャンクを補う（純粋関数）。

    固定パイプライン（pipeline.analyze）とエージェント（agent.run）が共有する後段処理。
    引数:
      judged_results : LLM が返した results（各要素は id と判定フィールドを持つ）
      rec_by_id      : id -> record（file/heading_path/content を持つ）の辞書
    戻り値: file/heading_path/content を補った要素の配列。存在しない id の要素は捨てる。
    """
    enriched = []
    for item in judged_results:
        rec = rec_by_id.get(item["id"])
        if rec is None:
            continue  # 存在しない id（取り違え・捏造）は捨てる
        enriched.append({
            **item,
            "file": rec["file"],
            "heading_path": rec["heading_path"],
            "content": rec["content"],
        })
    return enriched
