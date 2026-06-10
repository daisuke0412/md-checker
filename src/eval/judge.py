import os
import sys
import json
import datetime

from ..config import config
from .. import utils  # Anthropic クライアント・トレースログは utils に一元化

# 採点結果の構造化スキーマ（judge 専用の tool）
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

def build_prompt(record: dict) -> str:
    """1 つの eval レコードの input/output を採点プロンプトに差し込む。"""
    input_text = json.dumps(record.get("input"), ensure_ascii=False, indent=2)
    output_text = json.dumps(record.get("output"), ensure_ascii=False, indent=2)
    return utils.fill_template(config.JUDGE_PROMPT_PATH, input=input_text, output=output_text)


def score_record(record: dict):
    """1 ペアを Claude に採点させ、(構造化採点 dict, request, 応答オブジェクト) を返す。

    クライアントは utils 共有のものを使うが、ここでは utils.get_anthropic() を直接叩き
    eval_logger を経由しない。これにより採点呼び出し自体は checker の入出力トレースに混ざらない。
    request と応答も返すのは、呼び出し側で judge 自身の LLM 入出力トレース（usage 込み）を残すため。
    """
    prompt = build_prompt(record)
    request = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": config.CLAUDE_MAX_TOKENS,
        "tools": [JUDGE_TOOL],
        "tool_choice": {"type": "tool", "name": JUDGE_TOOL["name"]},
        "messages": [{"role": "user", "content": prompt}],
    }
    response = utils.get_anthropic().messages.create(**request)
    for block in response.content:
        if block.type == "tool_use":
            return block.input, request, response
    raise RuntimeError(f"tool_use ブロックが応答に含まれていません: stop_reason={response.stop_reason}")


def log_llm_io(stamp: str, request: dict, response) -> None:
    """judge の LLM 入出力ペアを logs/judge/llm_io_YYYYMMDD.jsonl に 1 行追記する。

    checker の入出力トレース（logs/checker/llm_io_*.jsonl）と同形式（input/output ペア）。
    usage（トークン消費）は output（response）の中に含まれる。採点結果（scored_*.jsonl）とは
    別ファイルに残し、checker のトレースにも混ぜない（採点呼び出しが次の採点対象に混ざるのを防ぐ）。
    """
    io_record = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "input": request,
        "output": response.model_dump(),
    }
    os.makedirs(config.JUDGE_LOG_DIR, exist_ok=True)
    path = os.path.join(config.JUDGE_LOG_DIR, f"llm_io_{stamp}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(io_record, ensure_ascii=False, default=str) + "\n")


def _read_jsonl(path: str):
    """JSON Lines を 1 行ずつ dict にして返す（空行は飛ばす）。

    1 行 = 1 レコードが前提。indent 付き等で 1 レコードが複数行に割れていると
    パースに失敗するので、その行番号を添えて分かりやすく知らせる。
    """
    records = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"{path} の {lineno} 行目が JSON Lines として不正です（1 行 1 レコード必須）: {e}"
                ) from e
    return records


def main():
    logger = utils.create("eval_judge")

    # 採点対象の日付（既定は当日）。checker の LLM 入出力トレース llm_io_YYYYMMDD.jsonl を読む。
    stamp = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now().strftime("%Y%m%d")
    in_path = os.path.join(config.CHECKER_LLM_LOG_DIR, f"llm_io_{stamp}.jsonl")
    out_path = os.path.join(config.JUDGE_LOG_DIR, f"scored_{stamp}.jsonl")
    logger.write("採点対象", {"stamp": stamp, "in_path": in_path, "out_path": out_path, "model": config.CLAUDE_MODEL})

    if not os.path.exists(in_path):
        print(f"LLM 入出力トレースが見つかりません: {in_path}")
        logger.write("中断", f"LLM 入出力トレースが見つかりません: {in_path}")
        sys.exit(1)

    os.makedirs(config.JUDGE_LOG_DIR, exist_ok=True)

    records = _read_jsonl(in_path)
    print(f"採点します: {in_path}（{len(records)} 件, model={config.CLAUDE_MODEL}）")
    logger.write("読み込み件数", len(records))

    with open(out_path, "w", encoding="utf-8") as out:
        for i, record in enumerate(records, start=1):
            print(f"  採点中... {i}/{len(records)}")
            judge, request, response = score_record(record)
            logger.write("採点", {"index": i, "judge": judge})
            # judge 自身の LLM 入出力トレース（usage 込み）を別ファイルに記録（失敗しても採点本体は止めない）
            try:
                log_llm_io(stamp, request, response)
            except Exception as e:
                logger.write("LLM入出力トレースの記録に失敗", {"index": i, "error": str(e)})
            scored = {
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "source": record,
                "judge": judge,
                "judge_model": config.CLAUDE_MODEL,
            }
            out.write(json.dumps(scored, ensure_ascii=False, default=str) + "\n")

    print(f"\n書き出しました: {out_path}")
    logger.write("書き出し完了", {"out_path": out_path, "採点件数": len(records)})


if __name__ == "__main__":
    main()
