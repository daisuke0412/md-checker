import os
import json
import datetime

from ..config import config


class Logger:
    """1 ログファイルへの書き込み口。create() が生成して返す。"""

    def __init__(self, path: str):
        self.path = path

    def write(self, key: str, value) -> None:
        """1 行追記する: {現在時刻: now, key: value} の JSON 形式。"""
        now = datetime.datetime.now().isoformat(timespec="seconds")
        record = {"現在時刻": now, key: value}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def create(name: str) -> Logger:
    """ログファイルを 1 つ作り、それに書き込む Logger を返す。

    例: logs/trace/20260608-153000_pipeline.log
    """
    os.makedirs(config.TRACE_LOG_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(config.TRACE_LOG_DIR, f"{stamp}_{name}.log")
    open(path, "a", encoding="utf-8").close()
    return Logger(path)
