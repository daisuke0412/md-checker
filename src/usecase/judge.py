import datetime
import json
import os
import sys

from ..config import config
from ..infra.llm import run as llm_run
from ..infra.output_schemas import JUDGE_OUTPUT_SCHEMA

_REPORT_TOOL_NAMES = {"report_similar", "report_conflicts"}


def _is_report_record(record: dict) -> bool:
    """ログレコードが report ターン（最終判定）かどうか判定する。"""
    content = record.get("response", {}).get("content", [])
    return any(
        block.get("type") == "tool_use" and block.get("name") in _REPORT_TOOL_NAMES
        for block in content
    )


def _extract_user_message(record: dict) -> str:
    """request の最初のユーザーメッセージ（入力クエリ + 候補）を取り出す。"""
    messages = record.get("request", {}).get("messages", [])
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
    return ""


def _extract_report(record: dict) -> dict:
    """response から report_similar / report_conflicts の input を取り出す。"""
    content = record.get("response", {}).get("content", [])
    for block in content:
        if block.get("type") == "tool_use" and block.get("name") in _REPORT_TOOL_NAMES:
            return {"tool": block.get("name"), "result": block.get("input", {})}
    return {}


def score_record(record: dict, system: str) -> dict:
    user_message = _extract_user_message(record)
    report = _extract_report(record)
    report_json = json.dumps(report, ensure_ascii=False, indent=2)

    user_msg = (
        f"md-checker への入力と判定結果:\n"
        f"<input_and_candidates>\n{user_message}\n</input_and_candidates>\n\n"
        f"<report>\n{report_json}\n</report>"
    )

    response = llm_run(
        messages=[{"role": "user", "content": user_msg}],
        tools=[JUDGE_OUTPUT_SCHEMA],
        tool_choice={"type": "tool", "name": JUDGE_OUTPUT_SCHEMA["name"]},
        system=system,
        log_to_eval=False,
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError(f"tool_use ブロックが応答に含まれていません: stop_reason={response.stop_reason}")


def main():
    stamp = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now().strftime("%Y%m%d")
    in_path = os.path.join(config.CHECKER_LLM_LOG_DIR, f"llm_io_{stamp}.jsonl")
    out_jsonl = os.path.join(config.JUDGE_LOG_DIR, f"scored_{stamp}.jsonl")
    out_summary = os.path.join(config.JUDGE_LOG_DIR, f"summary_{stamp}.txt")

    if not os.path.exists(in_path):
        print(f"LLM 入出力トレースが見つかりません: {in_path}")
        sys.exit(1)

    with open(config.JUDGE_PROMPT_PATH, encoding="utf-8") as f:
        system = f.read()

    all_records = []
    with open(in_path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                all_records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{in_path} の {lineno} 行目が不正です: {e}") from e

    records = [r for r in all_records if _is_report_record(r)]
    print(f"採点します: {in_path}（全 {len(all_records)} 件中 report ターン {len(records)} 件, model={config.CLAUDE_MODEL}）")

    os.makedirs(config.JUDGE_LOG_DIR, exist_ok=True)
    scored_list = []

    with open(out_jsonl, "w", encoding="utf-8") as out:
        for i, record in enumerate(records, start=1):
            print(f"  採点中... {i}/{len(records)}")
            judge = score_record(record, system)
            scored = {
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "source_timestamp": record.get("timestamp", ""),
                "tool": _extract_report(record).get("tool", ""),
                "judge": judge,
                "judge_model": config.CLAUDE_MODEL,
            }
            out.write(json.dumps(scored, ensure_ascii=False, default=str) + "\n")
            scored_list.append(scored)

    # サマリー出力
    with open(out_summary, "w", encoding="utf-8") as f:
        lines = [
            f"採点サマリー {stamp}\n",
            f"対象: {in_path}\n",
            f"件数: {len(scored_list)}\n",
            "=" * 60 + "\n\n",
        ]
        for s in scored_list:
            j = s["judge"]
            lines.append(f"[{s['source_timestamp']}] {s['tool']}\n")
            lines.append(f"  score : {j.get('score')} / label: {j.get('label')}\n")
            lines.append(f"  reason: {j.get('reason')}\n")
            for issue in j.get("issues", []):
                lines.append(f"  issue : {issue}\n")
            lines.append("\n")
        f.writelines(lines)

    print(f"\n書き出しました:")
    print(f"  詳細: {out_jsonl}")
    print(f"  サマリー: {out_summary}")


if __name__ == "__main__":
    main()
