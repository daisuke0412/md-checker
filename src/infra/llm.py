import os
import json
import datetime

from dotenv import load_dotenv
import anthropic

from ..config import config

_anthropic_client = None
_env_loaded = False


def _load_env_once() -> None:
    global _env_loaded
    if not _env_loaded:
        load_dotenv(config.ENV_PATH)
        _env_loaded = True


def _get_anthropic() -> "anthropic.Anthropic":
    global _anthropic_client
    if _anthropic_client is None:
        _load_env_once()
        _anthropic_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _anthropic_client


def run(
    messages: list,
    tools: list,
    tool_choice: dict,
    max_tokens: int = config.CLAUDE_MAX_TOKENS,
    system: str = None,
    log_to_eval: bool = True,
):
    """会話列と複数ツールを渡して Claude を 1 ターン呼び、応答オブジェクトをそのまま返す。

    log_to_eval=True（既定）のとき、LLM 入出力ペアを checker の評価ログ
    (logs/checker/llm_io_YYYYMMDD.jsonl) に自動記録する。
    judge は log_to_eval=False で呼ぶことで、採点呼び出し自体がチェッカーの
    評価対象ログに混入するのを防ぐ（意図的な分離）。
    """
    request = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "tools": tools,
        "tool_choice": tool_choice,
        "messages": messages,
    }
    if system is not None:
        request["system"] = system

    response = _get_anthropic().messages.create(**request)

    if log_to_eval:
        _log_checker_pair(request, response)

    return response


def complete(
    prompt: str,
    tool_schema: dict,
    max_tokens: int = config.CLAUDE_MAX_TOKENS,
) -> dict:
    """完成済みのプロンプトを Claude に投げ、tool_schema に沿った構造化データ(dict)を返す。

    run() に「単一プロンプト＋単一スキーマを tool 強制で 1 回通す」薄いラッパ。
    """
    response = run(
        messages=[{"role": "user", "content": prompt}],
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": tool_schema["name"]},
        max_tokens=max_tokens,
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError(f"tool_use ブロックが応答に含まれていません: stop_reason={response.stop_reason}")


def _log_checker_pair(request: dict, response) -> None:
    """checker の LLM 入出力ペアを評価用ログに 1 行追記する。

    ログ書き込みの失敗で本処理（LLM 呼び出し）を止めないよう、例外は握りつぶす。
    """
    record = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "input": request,
        "output": response.model_dump(),
    }
    try:
        os.makedirs(config.CHECKER_LLM_LOG_DIR, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d")
        path = os.path.join(config.CHECKER_LLM_LOG_DIR, f"llm_io_{stamp}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as e:  # noqa: BLE001 - 評価ログ失敗で LLM 処理を止めない
        print(f"[警告] 評価ログの書き出しに失敗しました: {e}")
