import sys

from ..config import config
from ..usecase import agent


def _heading(path_list) -> str:
    return " > ".join(path_list) if path_list else "(見出しなし)"


def print_similarity(results):
    for i, item in enumerate(results, start=1):
        print(f"【類似 {i}】{item['file']}  {_heading(item['heading_path'])}")
        print(f"  似ている点: {item['reason']}")
        print(f"  該当箇所　: {item['excerpt']}")
        print()


def print_contradiction(results):
    for i, item in enumerate(results, start=1):
        print(f"【矛盾 {i}】{item['file']}  {_heading(item['heading_path'])}")
        print(f"  入力側の主張　: {item['claim']}")
        print(f"  既存文書の記載: {item['conflicting']}")
        print(f"  理由　　　　　: {item['reason']}")
        print()


def main():
    print("=== md-checker ===")
    print("機能を選んでください:")
    print("  1: 類似記載の検索")
    print("  2: 矛盾チェック")
    feature = input("番号を入力 > ").strip()

    if feature not in ("1", "2"):
        print("1 か 2 を入力してください。")
        sys.exit(1)

    if feature == "1":
        mode = config.Mode.SIMILARITY
        formatter = print_similarity
        label = "類似記載を検索"
    else:
        mode = config.Mode.CONTRADICTION
        formatter = print_contradiction
        label = "矛盾をチェック"

    print(f"\n確認したい文章を入力してください（最大 {config.MAX_INPUT_CHARS} 文字）:")
    query = input("> ").strip()
    if not query:
        print("入力が空です。")
        sys.exit(1)
    if len(query) > config.MAX_INPUT_CHARS:
        print(f"入力が長すぎます（{len(query)} 文字）。{config.MAX_INPUT_CHARS} 文字以内にしてください。")
        sys.exit(1)

    print(f"\n{label}しています...")
    result = agent.run(mode, query)

    print()
    results = result["results"]
    if results:
        formatter(results)
    else:
        print("該当する候補が見つかりませんでした。")


if __name__ == "__main__":
    main()
