from ...config import config
from ... import utils  # Anthropic クライアントは utils に一元化（utils.get_anthropic）
from . import eval_logger  # LLM 入出力の評価用ログ（llm_client からのみ呼ぶ）


def run(messages: list, tools: list, tool_choice: dict,
        max_tokens: int = config.CLAUDE_MAX_TOKENS, system: str = None):
    """会話列と複数ツールを渡して Claude を 1 ターン呼び、応答オブジェクトをそのまま返す。

    固定パイプライン（complete 経由）もエージェント（run 直接・ループ）も、この 1 か所で
    Claude を呼ぶ。評価用ログ（LLM 入出力ペア）の記録もここに集約する。これにより
    どちらの経路も自動で同じ評価対象に乗り、LLM-as-judge で同一の物差しで比較できる。

    引数:
      messages    : Anthropic messages 形式の会話列
      tools       : 渡すツール（tool スキーマ）の配列
      tool_choice : ツール選択モード（{"type": "auto"} / {"type": "tool", "name": ...} など）
      system      : システムプロンプト（任意。エージェントの行動指針に使う）
    戻り値: Anthropic SDK の応答オブジェクト（tool_use ブロックの取り出しは呼び出し側）。
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
    response = utils.get_anthropic().messages.create(**request)

    # 評価用に LLM 入出力をペアで記録する（入力=request そのまま, 出力=response そのまま）
    eval_logger.log_pair(request, response)
    return response


def complete(prompt: str, tool_schema: dict, max_tokens: int = config.CLAUDE_MAX_TOKENS) -> dict:
    """完成済みのプロンプトを Claude に投げ、tool_schema に沿った構造化データ(dict)を返す。

    run() に「単一プロンプト＋単一スキーマを tool 強制で 1 回通す」薄いラッパ。
    tool_choice でツールを強制呼び出しさせ、その入力(tool_use.input)を
    パース済みの dict として受け取る（テキスト応答や JSON パースは挟まない）。
    """
    response = run(
        messages=[{"role": "user", "content": prompt}],
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": tool_schema["name"]},
        max_tokens=max_tokens,
    )

    # tool_choice で強制したので、応答には必ず tool_use ブロックが含まれる
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError(f"tool_use ブロックが応答に含まれていません: stop_reason={response.stop_reason}")
