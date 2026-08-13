from ..config import config

SIMILARITY_OUTPUT_SCHEMA = {
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

CONTRADICTION_OUTPUT_SCHEMA = {
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

JUDGE_OUTPUT_SCHEMA = {
    "name": "report_score",
    "description": "md-checker の 1 出力を採点して返す。入力と出力だけを根拠に妥当性を評価する。",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "description": "1〜10 の整数（10=完全に妥当, 5=部分的, 1=不当）"},
            "label": {"type": "string", "enum": ["good", "partial", "bad"],
                      "description": "good=妥当 / partial=一部問題 / bad=重大な問題"},
            "reason": {"type": "string", "description": "採点理由の簡潔な説明"},
            "issues": {"type": "array", "items": {"type": "string"},
                       "description": "具体的な問題点。無ければ空配列"},
        },
        "required": ["score", "label", "reason", "issues"],
    },
}

OUTPUT_SCHEMAS = {
    config.Mode.SIMILARITY: SIMILARITY_OUTPUT_SCHEMA,
    config.Mode.CONTRADICTION: CONTRADICTION_OUTPUT_SCHEMA,
}
