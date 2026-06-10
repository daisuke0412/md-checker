import os
import sys

from ..config import config
from . import pipeline
from . import agent
from . import file_input


def read_input_text() -> str:
    """確認したい文章を直接入力させ、対象テキストを返す。"""
    print(f"\n確認したい文章を入力してください（最大 {config.MAX_INPUT_CHARS} 文字）:")
    return input("> ").strip()


def read_input_path() -> str:
    """対象 Markdown ファイルのパスを入力させ、受け取る。"""
    print("\n対象の Markdown ファイルのパスを入力してください:")
    return input("> ").strip()


def _heading(item) -> str:
    """結果アイテムの見出しパスを表示用文字列にする。"""
    return " > ".join(item["heading_path"]) if item["heading_path"] else "(見出しなし)"


def print_similarity(results):
    """類似検索の結果を整形表示する。"""
    for i, item in enumerate(results, start=1):
        print(f"【類似 {i}】{item['file']}  {_heading(item)}")
        print(f"  似ている点: {item['reason']}")
        print(f"  該当箇所　: {item['excerpt']}")
        print()


def print_contradiction(results):
    """矛盾チェックの結果を整形表示する。"""
    for i, item in enumerate(results, start=1):
        print(f"【矛盾 {i}】{item['file']}  {_heading(item)}")
        print(f"  入力側の主張　: {item['claim']}")
        print(f"  既存文書の記載: {item['conflicting']}")
        print(f"  理由　　　　　: {item['reason']}")
        print()


def _input_heading(path_list) -> str:
    """入力チャンクの見出しパスを表示用文字列にする。"""
    return " > ".join(path_list) if path_list else "(見出しなし)"


def print_file_report(report, formatter):
    """ファイル単位レポートを、入力チャンク軸でグルーピングして表示する。"""
    summary = report["summary"]
    print(f"■ ファイル: {report['file']}")
    print(f"  入力チャンク {summary['chunks']} 件中 {summary['hit_chunks']} 件で該当"
          f"（合計 {summary['results']} 件）")
    print()

    if not report["by_chunk"]:
        print("該当する候補が見つかりませんでした。")
        return

    for block in report["by_chunk"]:
        print(f"── 入力箇所: {_input_heading(block['input_heading'])} ──")
        formatter(block["results"])


def main():
    print("=== md-patrol ===")
    print("機能を選んでください:")
    print("  1: 類似記載の検索")
    print("  2: 矛盾チェック")
    feature = input("番号を入力 > ").strip()

    if feature not in ("1", "2"):
        print("1 か 2 を入力してください。")
        sys.exit(1)

    print("\n実行方法を選んでください:")
    print("  1: 固定パイプライン（1 回検索 → 1 回判定）")
    print("  2: エージェント（必要に応じて追加検索しながら判定）")
    engine_choice = input("番号を入力 > ").strip()

    if engine_choice not in ("1", "2"):
        print("1 か 2 を入力してください。")
        sys.exit(1)

    print("\n入力単位を選んでください:")
    print("  1: テキスト（確認したい文章を直接入力）")
    print("  2: ファイル（Markdown ファイル 1 本をまるごとチェック）")
    unit_choice = input("番号を入力 > ").strip()

    if unit_choice not in ("1", "2"):
        print("1 か 2 を入力してください。")
        sys.exit(1)

    mode = config.Mode.SIMILARITY if feature == "1" else config.Mode.CONTRADICTION
    formatter = print_similarity if feature == "1" else print_contradiction
    # 戦略を選ぶ。どちらも (mode, query, exclude_file) -> {"results": [...]} の同じ呼び口
    engine = pipeline.analyze if engine_choice == "1" else agent.run
    label = {"1": "類似記載を検索", "2": "矛盾をチェック"}[feature]

    if unit_choice == "1":
        # テキスト単位: 1 入力＝1 クエリ＝1 判定
        query = read_input_text()
        if not query:
            print("入力が空です。")
            sys.exit(1)
        if len(query) > config.MAX_INPUT_CHARS:
            print(f"入力が長すぎます（{len(query)} 文字）。{config.MAX_INPUT_CHARS} 文字以内にしてください。")
            sys.exit(1)

        print(f"\n{label}しています...")
        result = engine(mode, query)

        print()
        results = result["results"]
        if results:
            formatter(results)
        else:
            print("該当する候補が見つかりませんでした。")
    else:
        # ファイル単位: 入力をチャンク化し、チャンクごとに戦略を回して集約
        path = read_input_path()
        if not path:
            print("入力が空です。")
            sys.exit(1)
        if not os.path.isfile(path):
            print(f"ファイルが見つかりません: {path}")
            sys.exit(1)

        print(f"\n{label}しています（ファイル単位）...")
        report = file_input.analyze_file(engine, mode, path)

        print()
        print_file_report(report, formatter)


if __name__ == "__main__":
    main()
