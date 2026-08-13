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

    log_to_eval=True（既定）のとき、レスポンスを checker の評価ログに自動記録する。
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
        _log_llm_io(request, response)

    return response


def _log_llm_io(request, response) -> None:
    record = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "request": request,
        "response": response.model_dump(),
    }
    try:
        os.makedirs(config.CHECKER_LLM_LOG_DIR, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d")
        path = os.path.join(config.CHECKER_LLM_LOG_DIR, f"llm_io_{stamp}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as e:  # noqa: BLE001 - 評価ログ失敗で LLM 処理を止めない
        print(f"[警告] 評価ログの書き出しに失敗しました: {e}")
