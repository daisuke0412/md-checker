from ..config import config

# モード → プロンプト txt の対応（パスは config に集約）
_MODES = {
    config.Mode.SIMILARITY: config.SIMILARITY_PROMPT_PATH,
    config.Mode.CONTRADICTION: config.CONTRADICTION_PROMPT_PATH,
}


def build_candidates_block(results) -> str:
    """hybrid_search の結果 [(score, record), ...] を候補ブロックに整形する。"""
    lines = []
    for _score, rec in results:
        heading = " > ".join(rec["heading_path"]) if rec["heading_path"] else "(見出しなし)"
        lines.append(f"=== 候補 (id: {rec['id']}) ===")
        lines.append(f"ファイル: {rec['file']}")
        lines.append(f"見出し: {heading}")
        lines.append(f"本文:\n{rec['content']}")
        lines.append("")
    return "\n".join(lines)


def build(mode: config.Mode, query: str, results) -> str:
    """モードに応じたプロンプト txt を読み込み、入力(query)と候補(results)を差し込んで返す。"""
    if mode not in _MODES:
        raise ValueError(f"未知のモードです: {mode}（config.Mode のいずれか）")
    candidates_block = build_candidates_block(results)
    return _fill_template(_MODES[mode], input=query, candidates=candidates_block)


def build_judge_prompt(path: str, input_text: str, output_text: str) -> str:
    """judge 用のプロンプトを組み立てる。"""
    return _fill_template(path, input=input_text, output=output_text)


def _fill_template(path: str, **fields: str) -> str:
    """テンプレ txt を読み込み、各 {key} を fields[key] で置換して返す。

    JSON 例などにテンプレ自身が { } を含むため、str.format ではなく replace で
    必要なキーだけを差し替える（想定外の中括弧を壊さない）。
    """
    with open(path, encoding="utf-8") as f:
        template = f.read()
    for key, value in fields.items():
        template = template.replace("{" + key + "}", value)
    return template
