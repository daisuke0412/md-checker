from ..config import config
from ..domain.retrieval.hybrid import hybrid_search
from ..infra.embedder import embed_query
from ..infra.llm import run as llm_run
from ..infra.store import get_store
from ..infra.output_schemas import OUTPUT_SCHEMAS
from ..infra.tools import agent_tools

# mode -> エージェント用システムプロンプト（行動指針＋判定基準）のパス
_AGENT_PROMPT_PATHS = {
    config.Mode.SIMILARITY: config.AGENT_SIMILARITY_PROMPT_PATH,
    config.Mode.CONTRADICTION: config.AGENT_CONTRADICTION_PROMPT_PATH,
}


def _load_system_prompt(mode: config.Mode) -> str:
    with open(_AGENT_PROMPT_PATHS[mode], encoding="utf-8") as f:
        return f.read()


def _format_candidates(results) -> str:
    lines = []
    for _score, rec in results:
        heading = " > ".join(rec["heading_path"]) if rec["heading_path"] else "(見出しなし)"
        lines.append(f"=== 候補 (id: {rec['id']}) ===")
        lines.append(f"ファイル: {rec['file']}")
        lines.append(f"見出し: {heading}")
        lines.append(f"本文:\n{rec['content']}")
        lines.append("")
    return "\n".join(lines)


def _register_and_format(recs: list, sent_records: dict) -> str:
    """新規 record を sent_records に登録し、候補ブロックを返す。"""
    fresh = [rec for rec in recs if rec["id"] not in sent_records]
    for rec in fresh:
        sent_records[rec["id"]] = rec
    return _format_candidates((None, rec) for rec in fresh) if fresh else ""


def run(mode: config.Mode, query: str) -> dict:
    # クエリをベクトル化して初期候補を検索
    query_vec = embed_query(query)

    # ベクトルストアを取得し、初期候補を検索する
    store = get_store()
    initial = hybrid_search(store.records, query, query_vec, k=config.CANDIDATE_K)

    # LLM への最初のユーザーメッセージを作成（入力クエリ + 初期候補）
    candidates_block = _format_candidates(initial) or "（候補なし。search で探してください）"
    user_msg = (
        f"入力テキスト:\n<input>\n{query}\n</input>\n\n"
        f"既存文書の候補（検索で集めたもの）:\n<candidates>\n{candidates_block}\n</candidates>"
    )
    messages = [{"role": "user", "content": user_msg}]

    sent_records = {}
    for _score, rec in initial:
        sent_records[rec["id"]] = rec

    # システムプロンプトの読込
    system = _load_system_prompt(mode)
    # エージェントのツールを取得
    tools = agent_tools(mode)
    # 判定確定用の report ツール名を取得
    report_name = OUTPUT_SCHEMAS[mode]["name"]

    judged_results = None

    # エージェンティックループの開始（最大 MAX_AGENT_TURNS ターン）
    for turn in range(1, config.MAX_AGENT_TURNS + 1):

        # 最終ターンだけ report を強制し、それ以外は LLM に委ねる
        last_turn = turn == config.MAX_AGENT_TURNS
        tool_choice = ({"type": "tool", "name": report_name} if last_turn
                       else {"type": "auto"})

        response = llm_run(messages, tools, tool_choice, system=system,
                           log_to_eval=True)
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        finished = False
        for block in response.content:
            if block.type != "tool_use":
                continue

            # report_*: 判定確定。結果を控えてループを抜ける
            if block.name == report_name:
                judged_results = block.input.get("results", [])
                finished = True
                break

            # search: LLM のクエリで追加検索し、新規候補だけ返す
            if block.name == "search":
                search_vec = embed_query(block.input["query"])
                hits = hybrid_search(store.records, block.input["query"], search_vec,
                                     k=config.AGENT_SEARCH_K)
                content = _register_and_format([rec for _, rec in hits], sent_records)
                content = content or "（新しい候補はありません）"

            # expand: 起点 id の前後／同ファイルを取得し、新規候補だけ返す
            elif block.name == "expand":
                recs = store.expand(
                    block.input["id"],
                    scope=block.input.get("scope", "neighbors"),
                    neighbors=config.EXPAND_NEIGHBORS,
                )
                content = _register_and_format(recs, sent_records)
                content = content or "（新しい候補はありません。id が無効か、既出です）"

            else:
                content = f"未知のツールです: {block.name}"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })

        if finished:
            break

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            messages.append({"role": "user",
                             "content": "ツールを使うか、report で判定を確定してください。"})

    # 3. report が一度も得られなかった場合は空結果にフォールバック
    if judged_results is None:
        judged_results = []

    # 4. LLM が返した id を sent_records で元チャンクへ逆引き補完する
    enriched = []
    for item in judged_results:
        rec = sent_records.get(item["id"])
        if rec is not None:
            enriched.append({**item, "file": rec["file"], "heading_path": rec["heading_path"], "content": rec["content"]})
    return {"results": enriched}
