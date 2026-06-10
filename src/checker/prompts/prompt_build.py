from ...config import config
from ... import utils  # テンプレ組立は共有層に一元化（utils.fill_template）

# モード → プロンプト txt の対応（パスは config に集約）
MODES = {
    config.Mode.SIMILARITY: config.SIMILARITY_PROMPT_PATH,
    config.Mode.CONTRADICTION: config.CONTRADICTION_PROMPT_PATH,
}

# モード → Claude に渡す tool スキーマ。Claude はこのスキーマに沿った構造化データを返す。
# 出典は候補の id で参照する（file/heading は呼び出し元が id から逆引きするので持たせない）。
SIMILARITY_TOOL = {
    "name": "report_similar",
    "description": "入力テキストと類似する既存文書の候補を、似ている度合いが高い順に報告する。"
                   "類似する候補が無ければ results を空配列にする。",
    "input_schema": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "description": "類似すると判断した候補のみ。似ている度合いが高い順。",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "その候補の id（渡された候補の id をそのまま）"},
                        "reason": {"type": "string", "description": "入力のどの点と、どう似ているかの簡潔な説明"},
                        "excerpt": {"type": "string", "description": "似ていると判断した該当箇所の短い引用（本文から抜粋）"},
                    },
                    "required": ["id", "reason", "excerpt"],
                },
            },
        },
        "required": ["results"],
    },
}

CONTRADICTION_TOOL = {
    "name": "report_conflicts",
    "description": "入力テキストの主張と食い違う既存文書の記載を、確からしさが高い順に報告する。"
                   "矛盾する候補が無ければ results を空配列にする。",
    "input_schema": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "description": "矛盾すると判断した候補のみ。確からしさが高い順。",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "その候補の id（渡された候補の id をそのまま）"},
                        "claim": {"type": "string", "description": "入力テキスト側の主張（矛盾している部分）"},
                        "conflicting": {"type": "string", "description": "既存文書側の食い違う記載（本文からの短い引用）"},
                        "reason": {"type": "string", "description": "なぜ矛盾なのかの簡潔な説明"},
                    },
                    "required": ["id", "claim", "conflicting", "reason"],
                },
            },
        },
        "required": ["results"],
    },
}

TOOL_SCHEMAS = {
    config.Mode.SIMILARITY: SIMILARITY_TOOL,
    config.Mode.CONTRADICTION: CONTRADICTION_TOOL,
}

# --- エージェント用の追加ツール（検索を道具として LLM に持たせる）---------------
# report_* と違い、これらは「候補を増やす」道具。report_* が呼ばれたらループ終了。
SEARCH_TOOL = {
    "name": "search",
    "description": "追加の候補を検索する。入力テキストの言い換えや、特定の主張だけを抜き出した"
                   "クエリで引き直せる。まだ提示していない候補だけが返る。",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "検索クエリ（言い換え・主張の抜き出しなど自由に組み立てる）"},
        },
        "required": ["query"],
    },
}

EXPAND_TOOL = {
    "name": "expand",
    "description": "指定した候補と同じファイルの前後チャンク（または全チャンク）を取り寄せる。"
                   "数値・定義など、候補本文だけでは判断しきれない文脈を補うのに使う。",
    "input_schema": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "起点にする候補の id（提示済みのもの）"},
            "scope": {"type": "string", "enum": ["neighbors", "same_file"],
                      "description": "neighbors=前後の数チャンク（既定） / same_file=同ファイル全チャンク"},
        },
        "required": ["id"],
    },
}


def agent_tools(mode: config.Mode) -> list:
    """エージェントに渡すツール配列を返す: [search, expand, report_*(mode に応じて)]。"""
    if mode not in TOOL_SCHEMAS:
        raise ValueError(f"未知のモードです: {mode}（config.Mode のいずれか）")
    return [SEARCH_TOOL, EXPAND_TOOL, TOOL_SCHEMAS[mode]]


def build_candidates_block(results) -> str:
    """hybrid_search の結果 [(score, record), ...] を候補ブロックに整形する。"""
    lines = []
    for _score, rec in results:
        heading = " > ".join(rec["heading_path"]) if rec["heading_path"] else "(見出しなし)"
        lines.append(f"=== 候補 (id: {rec['id']}) ===")  # Claude が出典を id で参照できるように
        lines.append(f"ファイル: {rec['file']}")
        lines.append(f"見出し: {heading}")
        lines.append(f"本文:\n{rec['content']}")
        lines.append("")
    return "\n".join(lines)


def build(mode: config.Mode, query: str, results) -> str:
    """モードに応じたプロンプト txt を読み込み、入力(query)と候補(results)を差し込んで返す。"""
    if mode not in MODES:
        raise ValueError(f"未知のモードです: {mode}（config.Mode のいずれか）")

    candidates_block = build_candidates_block(results)
    return utils.fill_template(MODES[mode], input=query, candidates=candidates_block)
