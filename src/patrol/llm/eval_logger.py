"""
eval_logger.py — patrol の LLM 入出力トレース

LLM の「入力（messages.create に渡した引数）」と「出力（response）」をペアで 1 行ずつ
日次ファイルに追記する。このログ自体は採点結果を持たない（後で LLM-as-judge がこれを読み、
採点は元ログに書き戻さず別ファイル logs/judge/scored_YYYYMMDD.jsonl に出力する。判定は eval/judge.py）。

llm_client.complete からのみ呼ぶ（LLM 機能に閉じた関心事なので llm フォルダ内に置く）。
ファイルは期間（日次）単位の追記型 JSON Lines: logs/patrol/llm_io_YYYYMMDD.jsonl
"""

import os
import json
import datetime

from ...config import config  # 出力先（PATROL_LLM_LOG_DIR）は設定の集約点から参照


def log_pair(request: dict, response) -> None:
    """1 つの LLM 入出力ペアを評価用ログに 1 行追記する。

    引数:
      request  : messages.create に渡した引数そのまま（model/tools/messages 等）。input として保存。
      response : Anthropic SDK の応答オブジェクト。model_dump() で dict 化して output に保存。

    採点結果はこのログには持たせない（judge.py が source/judge を持つ別ファイルに書き出す）。
    ログ書き込みの失敗で本処理（LLM 呼び出し）を止めないよう、例外は握りつぶす。
    """
    record = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "input": request,
        "output": response.model_dump(),
    }
    try:
        os.makedirs(config.PATROL_LLM_LOG_DIR, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d")
        path = os.path.join(config.PATROL_LLM_LOG_DIR, f"llm_io_{stamp}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as e:  # noqa: BLE001 - 評価ログ失敗で LLM 処理を止めない
        print(f"[警告] 評価ログの書き出しに失敗しました: {e}")
