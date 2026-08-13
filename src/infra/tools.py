from ..config import config
from .output_schemas import OUTPUT_SCHEMAS

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
    """エージェントに渡すツール配列を返す: [search, expand, output_schema(mode に応じて)]。"""
    if mode not in OUTPUT_SCHEMAS:
        raise ValueError(f"未知のモードです: {mode}（config.Mode のいずれか）")
    return [SEARCH_TOOL, EXPAND_TOOL, OUTPUT_SCHEMAS[mode]]
