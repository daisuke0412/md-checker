from ..config import config
from .rag_search import hybrid_search
from .llm import llm_client
from .prompts import prompt_build
from .. import utils


def enrich(judged_results, rec_by_id) -> list:
    """LLM の判定（id＋reason 等）に、id で逆引きした元チャンクを補う。

    固定パイプライン（analyze）とエージェント（agent.run）が共有する後段処理。
    引数:
      judged_results : LLM が返した results（各要素は id と判定フィールドを持つ）
      rec_by_id      : id -> record（file/heading_path/content を持つ）の辞書
    戻り値: file/heading_path/content を補った要素の配列。存在しない id の要素は捨てる。
    """
    enriched = []
    for item in judged_results:
        rec = rec_by_id.get(item["id"])
        if rec is None:
            continue  # 存在しない id（取り違え・捏造）は捨てる
        enriched.append({
            **item,
            "file": rec["file"],
            "heading_path": rec["heading_path"],
            "content": rec["content"],
        })
    return enriched


def analyze(mode: config.Mode, query: str, exclude_file: str = None) -> dict:
    """入力テキストを RAG＋Claude で分析し、構造化した結果(dict)を返す。

    引数:
      mode  : config.Mode.SIMILARITY（類似検索）または config.Mode.CONTRADICTION（矛盾チェック）
      query : ユーザーの入力テキスト
      exclude_file : 同名ファイルを候補から除外する（ファイル単位入力の自己マッチ回避。
                     docs/design/pipeline.md 7.2）。テキスト単位・新規ファイルでは None。
    戻り値: {"results": [...]}。各要素は Claude の判定（id・reason 等）に、id で逆引きした
            元チャンクの file/heading/content を補ったもの。該当・候補が無ければ results は空配列。
    """
    logger = utils.create(f"pipeline_{mode.value}")
    logger.write("モード", mode.value)
    logger.write("ユーザークエリ", query)
    if exclude_file:
        logger.write("除外ファイル", exclude_file)
    logger.write("config", {
        k: v for k, v in vars(config).items()
        if k.isupper() and not k.startswith("_")
    })

    # 1. CANDIDATE_K 個の候補を集める（その後 Claude で取捨選択）
    results = hybrid_search.search(query, exclude_file=exclude_file)
    if not results:
        logger.write("RAG検索結果", [])
        return {"results": []}  # 検索ヒットゼロも「該当なし」として空配列に揃える

    logger.write("RAG検索結果", results)

    # 2. 候補と入力を mode に応じたプロンプトに組み立て、tool スキーマと共に Claude へ
    prompt = prompt_build.build(mode, query, results)
    logger.write("プロンプト", prompt)

    judged = llm_client.complete(prompt, prompt_build.TOOL_SCHEMAS[mode])
    logger.write("LLM出力", judged)

    # 3. Claude が返した id から元チャンクを逆引きし、file/heading/content を補う
    rec_by_id = {rec["id"]: rec for _score, rec in results}
    enriched = enrich(judged.get("results", []), rec_by_id)

    logger.write("最終結果", {"results": enriched})
    return {"results": enriched}
