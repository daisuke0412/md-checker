import os
import sys
import json
import datetime

from ..config import config
from ..infra.prompt import build_judge_prompt
from ..infra.tools import JUDGE_TOOL
from ..infra.llm import run as llm_run
from ..infra.logger import create


def score_record(record: dict):
    """1 ペアを Claude に採点させ、(構造化採点 dict, request, 応答オブジェクト) を返す。

    log_to_eval=False で呼ぶことで、採点呼び出し自体は checker の入出力トレースに混ざらない
    （judge の LLM 呼び出しを checker の評価対象ログに混入させないための意図的分離）。
    """
    input_text = json.dumps(record.get("input"), ensure_ascii=False, indent=2)
    output_text = json.dumps(record.get("output"), ensure_ascii=False, indent=2)
    prompt = build_judge_prompt(config.JUDGE_PROMPT_PATH, input_text, output_text)

    request_args = {
        "messages": [{"role": "user", "content": prompt}],
        "tools": [JUDGE_TOOL],
        "tool_choice": {"type": "tool", "name": JUDGE_TOOL["name"]},
    }
    response = llm_run(
        messages=request_args["messages"],
        tools=request_args["tools"],
        tool_choice=request_args["tool_choice"],
        log_to_eval=False,
    )
    # request を log_llm_io に渡すため再構築（llm.run が request dict を返さないため）
    full_request = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": config.CLAUDE_MAX_TOKENS,
        **request_args,
    }
    for block in response.content:
        if block.type == "tool_use":
            return block.input, full_request, response
    raise RuntimeError(f"tool_use ブロックが応答に含まれていません: stop_reason={response.stop_reason}")


def log_llm_io(stamp: str, request: dict, response) -> None:
    """judge の LLM 入出力ペアを logs/judge/llm_io_YYYYMMDD.jsonl に 1 行追記する。"""
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
    logger = create("eval_judge")

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
