from ..config import config
from ..domain.retrieval.hybrid import hybrid_search
from ..domain.retrieval.enrich import enrich
from ..infra.embedder import embed_query
from ..infra.store import load_records, get_index
from ..infra.llm import run as llm_run
from ..infra.prompt import build_candidates_block
from ..infra.tools import agent_tools, TOOL_SCHEMAS
from ..infra.logger import create

# mode -> エージェント用システムプロンプト（行動指針＋判定基準）のパス
_AGENT_PROMPT_PATHS = {
    config.Mode.SIMILARITY: config.AGENT_SIMILARITY_PROMPT_PATH,
    config.Mode.CONTRADICTION: config.AGENT_CONTRADICTION_PROMPT_PATH,
}


def _load_system_prompt(mode: config.Mode) -> str:
    with open(_AGENT_PROMPT_PATHS[mode], encoding="utf-8") as f:
        return f.read()


def _format_new_candidates(records, sent_ids: set) -> str:
    """まだ提示していない record だけを候補ブロックに整形する（提示済みは除く）。"""
    fresh = [rec for rec in records if rec["id"] not in sent_ids]
    if not fresh:
        return ""
    return build_candidates_block((None, rec) for rec in fresh)


def run(mode: config.Mode, query: str, exclude_file: str = None) -> dict:
    """入力テキストをツールループで分析し、pipeline.analyze と同形の {"results": [...]} を返す。"""
    logger = create(f"agent_{mode.value}")
    logger.write("モード", mode.value)
    logger.write("ユーザークエリ", query)
    if exclude_file:
        logger.write("除外ファイル", exclude_file)
    logger.write("config", {
        k: v for k, v in vars(config).items()
        if k.isupper() and not k.startswith("_")
    })

    index = get_index()
    sent_ids = set()
    sent_records = {}

    # 1. 初期候補を集めて会話を初期化する
    # 1-1. store を読み、exclude_file を候補から除外する（自己マッチ回避）
    records = load_records()
    if exclude_file is not None:
        records = [rec for rec in records if rec["file"] != exclude_file]

    # 1-2. ユーザー入力で 1 回検索し、得た候補を sent に登録する
    query_vec = embed_query(query)
    initial = hybrid_search(records, query, query_vec, k=config.CANDIDATE_K)
    for _score, rec in initial:
        sent_ids.add(rec["id"])
        sent_records[rec["id"]] = rec
    logger.write("初期候補", initial)

    # 1-3. 入力テキスト＋初期候補を最初のユーザーメッセージに組み立てる
    candidates_block = build_candidates_block(initial) or "（候補なし。search で探してください）"
    user_msg = (
        f"入力テキスト:\n<input>\n{query}\n</input>\n\n"
        f"既存文書の候補（検索で集めたもの）:\n<candidates>\n{candidates_block}\n</candidates>"
    )
    messages = [{"role": "user", "content": user_msg}]

    system = _load_system_prompt(mode)
    tools = agent_tools(mode)
    report_name = TOOL_SCHEMAS[mode]["name"]

    tool_calls = 0
    judged_results = None

    # 2. ツールループ（最大 MAX_AGENT_TURNS ターン）
    for turn in range(1, config.MAX_AGENT_TURNS + 1):
        # 2-1. 最終ターンだけ report を強制し、それ以外は LLM に委ねる
        last_turn = turn == config.MAX_AGENT_TURNS
        tool_choice = ({"type": "tool", "name": report_name} if last_turn
                       else {"type": "auto"})

        # 2-2. Claude を 1 ターン呼び、応答を会話に積む
        response = llm_run(messages, tools, tool_choice, system=system)
        logger.write("ターン", {"turn": turn, "stop_reason": response.stop_reason,
                                "tools": [b.name for b in response.content if b.type == "tool_use"]})

        messages.append({"role": "assistant", "content": response.content})

        # 2-3. 応答中の tool_use ブロックを順に処理する
        tool_results = []
        finished = False
        for block in response.content:
            if block.type != "tool_use":
                continue

            # 2-3-1. report_*: 判定確定。結果を控えてループを抜ける
            if block.name == report_name:
                judged_results = block.input.get("results", [])
                finished = True
                break

            tool_calls += 1
            # 2-3-2. search: LLM のクエリで追加検索し、新規候補だけ返す
            if block.name == "search":
                #   exclude を保ったまま store を読み直して検索
                search_records = load_records()
                if exclude_file is not None:
                    search_records = [rec for rec in search_records if rec["file"] != exclude_file]
                search_vec = embed_query(block.input["query"])
                hits = hybrid_search(search_records, block.input["query"], search_vec,
                                     k=config.AGENT_SEARCH_K)
                #   既出を除いた新規だけを LLM に提示し、sent に登録
                new_recs = [rec for _s, rec in hits if rec["id"] not in sent_ids]
                content = _format_new_candidates([r for _s, r in hits], sent_ids) or "（新しい候補はありません）"
                for rec in new_recs:
                    sent_ids.add(rec["id"])
                    sent_records[rec["id"]] = rec
                logger.write("search", {"query": block.input["query"], "新規候補数": len(new_recs)})

            # 2-3-3. expand: 起点 id の前後／同ファイルを取得し、新規候補だけ返す
            elif block.name == "expand":
                recs = index.expand(
                    block.input["id"],
                    scope=block.input.get("scope", "neighbors"),
                    neighbors=config.EXPAND_NEIGHBORS,
                )
                #   既出を除いた新規だけを LLM に提示し、sent に登録
                new_recs = [rec for rec in recs if rec["id"] not in sent_ids]
                content = _format_new_candidates(recs, sent_ids) or "（新しい候補はありません。id が無効か、既出です）"
                for rec in new_recs:
                    sent_ids.add(rec["id"])
                    sent_records[rec["id"]] = rec
                logger.write("expand", {"id": block.input["id"],
                                        "scope": block.input.get("scope", "neighbors"),
                                        "新規候補数": len(new_recs)})
            # 2-3-4. それ以外のツール名は想定外
            else:
                content = f"未知のツールです: {block.name}"

            # 2-3-5. 検索上限に達したら、以降は判定を促す注意書きを添える
            if tool_calls >= config.MAX_TOOL_CALLS:
                content += "\n\n（検索回数の上限に達しました。これ以上は検索できません。判定を確定してください。）"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })

        # 2-4. report が出ていれば終了。出ていなければ tool_result（無ければ催促）を返して次ターンへ
        if finished:
            break

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            messages.append({"role": "user",
                             "content": "ツールを使うか、report で判定を確定してください。"})

    # 3. report が一度も得られなかった場合は空結果にフォールバック
    if judged_results is None:
        logger.write("警告", "report_* が得られませんでした。空結果を返します。")
        judged_results = []

    logger.write("LLM出力", {"results": judged_results})

    # 4. LLM が返した id を、ループ中に集めた sent_records で元チャンクへ逆引き補完する
    enriched = enrich(judged_results, sent_records)
    logger.write("最終結果", {"results": enriched, "turn数": turn, "検索回数": tool_calls})
    return {"results": enriched}
