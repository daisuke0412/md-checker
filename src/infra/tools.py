from ..config import config

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

JUDGE_TOOL = {
    "name": "report_score",
    "description": "md-checker の 1 出力を採点して返す。入力と出力だけを根拠に妥当性を評価する。",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "description": "1〜5 の整数（5=完全に妥当, 3=部分的, 1=不当）"},
            "label": {"type": "string", "enum": ["good", "partial", "bad"],
                      "description": "good=妥当 / partial=一部問題 / bad=重大な問題"},
            "reason": {"type": "string", "description": "採点理由の簡潔な説明"},
            "issues": {"type": "array", "items": {"type": "string"},
                       "description": "具体的な問題点。無ければ空配列"},
        },
        "required": ["score", "label", "reason", "issues"],
    },
}


def agent_tools(mode: config.Mode) -> list:
    """エージェントに渡すツール配列を返す: [search, expand, report_*(mode に応じて)]。"""
    if mode not in TOOL_SCHEMAS:
        raise ValueError(f"未知のモードです: {mode}（config.Mode のいずれか）")
    return [SEARCH_TOOL, EXPAND_TOOL, TOOL_SCHEMAS[mode]]
