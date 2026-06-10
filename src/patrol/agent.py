"""
agent.py — 検索エージェント（ツールループ）

固定パイプライン（pipeline.analyze）と並ぶもう 1 つの戦略。検索を道具として LLM に持たせ、
確信が持てるまで search/expand で能動的に候補を集めてから report_* で判定を確定する
（設計は docs/design/agent.md）。戻り値は analyze と同形 {"results": [...]} で、後段の
補完（enrich）・表示は固定パイプラインと共有する。
"""

from ..config import config
from .rag_search import hybrid_search
from .rag_search import store_index
from .llm import llm_client
from .prompts import prompt_build
from . import pipeline  # enrich を共有
from .. import utils

# mode -> エージェント用システムプロンプト（行動指針＋判定基準）のパス
_AGENT_PROMPT_PATHS = {
    config.Mode.SIMILARITY: config.AGENT_SIMILARITY_PROMPT_PATH,
    config.Mode.CONTRADICTION: config.AGENT_CONTRADICTION_PROMPT_PATH,
}


def _load_system_prompt(mode: config.Mode) -> str:
    with open(_AGENT_PROMPT_PATHS[mode], encoding="utf-8") as f:
        return f.read()


def _format_new_candidates(records, seen_ids: set) -> str:
    """まだ提示していない record だけを候補ブロックに整形する（提示済みは除く）。

    prompt_build.build_candidates_block は [(score, rec), ...] を受けるので、score を
    持たない record はダミーの score で包んで渡す（整形は score を使わない）。
    """
    fresh = [rec for rec in records if rec["id"] not in seen_ids]
    if not fresh:
        return ""
    return prompt_build.build_candidates_block((None, rec) for rec in fresh)


def run(mode: config.Mode, query: str, exclude_file: str = None) -> dict:
    """入力テキストをツールループで分析し、analyze と同形の {"results": [...]} を返す。

    exclude_file を渡すと、初期候補・search の追加検索の両方で同名ファイルを除外する
    （ファイル単位入力の自己マッチ回避。docs/design/agent.md 10.2）。expand は提示済み
    候補（seen_ids）を起点にするため、自己ファイルの id はそもそも seen_ids に入らない。
    """
    logger = utils.create(f"agent_{mode.value}")
    logger.write("モード", mode.value)
    logger.write("ユーザークエリ", query)
    if exclude_file:
        logger.write("除外ファイル", exclude_file)
    logger.write("config", {
        k: v for k, v in vars(config).items()
        if k.isupper() and not k.startswith("_")
    })

    index = store_index.get_index()  # expand 用・ロード使い回し
    seen_ids = set()                 # 提示済み候補の id（重複除去＋実在性チェック）
    seen_records = {}                # id -> record（最後の enrich 用）

    # 1. 初期候補を集めて会話を初期化する
    initial = hybrid_search.search(query, exclude_file=exclude_file)
    for _score, rec in initial:
        seen_ids.add(rec["id"])
        seen_records[rec["id"]] = rec
    logger.write("初期候補", initial)

    candidates_block = prompt_build.build_candidates_block(initial) or "（候補なし。search で探してください）"
    user_msg = (
        f"入力テキスト:\n<input>\n{query}\n</input>\n\n"
        f"既存文書の候補（検索で集めたもの）:\n<candidates>\n{candidates_block}\n</candidates>"
    )
    messages = [{"role": "user", "content": user_msg}]

    system = _load_system_prompt(mode)
    tools = prompt_build.agent_tools(mode)
    report_name = prompt_build.TOOL_SCHEMAS[mode]["name"]

    tool_calls = 0          # search/expand の累計
    judged_results = None   # report_* が返した results

    # 2. ツールループ
    for turn in range(1, config.MAX_AGENT_TURNS + 1):
        # 最終ターンは report_* を強制し、必ず結果を出させる
        last_turn = turn == config.MAX_AGENT_TURNS
        tool_choice = ({"type": "tool", "name": report_name} if last_turn
                       else {"type": "auto"})

        response = llm_client.run(messages, tools, tool_choice, system=system)
        logger.write("ターン", {"turn": turn, "stop_reason": response.stop_reason,
                                "tools": [b.name for b in response.content if b.type == "tool_use"]})

        # assistant 応答を会話に追記
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []   # この応答内の tool_use への tool_result
        finished = False
        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == report_name:
                judged_results = block.input.get("results", [])
                finished = True
                break

            # search / expand は候補を増やす道具
            tool_calls += 1
            if block.name == "search":
                hits = hybrid_search.search(block.input["query"], k=config.AGENT_SEARCH_K,
                                            exclude_file=exclude_file)
                new_recs = [rec for _s, rec in hits if rec["id"] not in seen_ids]
                content = _format_new_candidates([r for _s, r in hits], seen_ids) or "（新しい候補はありません）"
                for rec in new_recs:
                    seen_ids.add(rec["id"])
                    seen_records[rec["id"]] = rec
                logger.write("search", {"query": block.input["query"], "新規候補数": len(new_recs)})

            elif block.name == "expand":
                recs = index.expand(
                    block.input["id"],
                    scope=block.input.get("scope", "neighbors"),
                    neighbors=config.EXPAND_NEIGHBORS,
                )
                new_recs = [rec for rec in recs if rec["id"] not in seen_ids]
                content = _format_new_candidates(recs, seen_ids) or "（新しい候補はありません。id が無効か、既出です）"
                for rec in new_recs:
                    seen_ids.add(rec["id"])
                    seen_records[rec["id"]] = rec
                logger.write("expand", {"id": block.input["id"],
                                        "scope": block.input.get("scope", "neighbors"),
                                        "新規候補数": len(new_recs)})
            else:
                content = f"未知のツールです: {block.name}"

            # 検索回数の上限に達したら、以降は判定確定を促す
            if tool_calls >= config.MAX_TOOL_CALLS:
                content += "\n\n（検索回数の上限に達しました。これ以上は検索できません。判定を確定してください。）"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })

        if finished:
            break

        # ツール結果を会話に積んで次ターンへ。tool_use が無ければ判定確定を促す
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            messages.append({"role": "user",
                             "content": "ツールを使うか、report で判定を確定してください。"})

    if judged_results is None:
        # 強制でも report が出なかった保険（通常は起きない）
        logger.write("警告", "report_* が得られませんでした。空結果を返します。")
        judged_results = []

    logger.write("LLM出力", {"results": judged_results})

    # 3. 出典の実在性チェック（提示済み候補に無い id は捨てる）と enrich（共通の後段）
    enriched = pipeline.enrich(judged_results, seen_records)
    logger.write("最終結果", {"results": enriched, "turn数": turn, "検索回数": tool_calls})
    return {"results": enriched}
