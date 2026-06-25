from ..config import config
from ..domain.retrieval.hybrid import hybrid_search
from ..domain.retrieval.enrich import enrich
from ..infra.embedder import embed_query
from ..infra.store import load_records
from ..infra.llm import complete
from ..infra.prompt import build as build_prompt
from ..infra.tools import TOOL_SCHEMAS
from ..infra.logger import create


def analyze(mode: config.Mode, query: str, exclude_file: str = None) -> dict:
    """入力テキストを RAG＋Claude で分析し、構造化した結果(dict)を返す。

    引数:
      mode         : config.Mode.SIMILARITY（類似検索）または config.Mode.CONTRADICTION（矛盾チェック）
      query        : ユーザーの入力テキスト
      exclude_file : 同名ファイルを候補から除外する（ファイル単位入力の自己マッチ回避）
    戻り値: {"results": [...]}
    """
    logger = create(f"pipeline_{mode.value}")
    logger.write("モード", mode.value)
    logger.write("ユーザークエリ", query)
    if exclude_file:
        logger.write("除外ファイル", exclude_file)
    logger.write("config", {
        k: v for k, v in vars(config).items()
        if k.isupper() and not k.startswith("_")
    })

    # 1. store を読み、除外して candidates を取得
    records = load_records()
    if exclude_file is not None:
        records = [rec for rec in records if rec["file"] != exclude_file]
    if not records:
        logger.write("RAG検索結果", [])
        return {"results": []}

    query_vec = embed_query(query)
    results = hybrid_search(records, query, query_vec, k=config.CANDIDATE_K)
    if not results:
        logger.write("RAG検索結果", [])
        return {"results": []}

    logger.write("RAG検索結果", results)

    # 2. プロンプトを組立て、tool 強制で 1 回判定
    prompt = build_prompt(mode, query, results)
    logger.write("プロンプト", prompt)

    judged = complete(prompt, TOOL_SCHEMAS[mode])
    logger.write("LLM出力", judged)

    # 3. id から元チャンクを逆引きして enrich
    rec_by_id = {rec["id"]: rec for _score, rec in results}
    enriched = enrich(judged.get("results", []), rec_by_id)

    logger.write("最終結果", {"results": enriched})
    return {"results": enriched}
