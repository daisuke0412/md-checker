"""プロンプト組立の共有ヘルパ（共有層）。

patrol（判定プロンプト）と eval（採点プロンプト）の双方が「テンプレ txt を読んで
プレースホルダを差し込む」組立を行う。その共通部分だけをここに一元化し、
各機能パッケージは固有の tool スキーマ・候補整形を自分のパッケージ側に持つ。
"""


def fill_template(path: str, **fields: str) -> str:
    """テンプレ txt を読み込み、各 {key} を fields[key] で置換して返す。

    JSON 例などにテンプレ自身が { } を含むため、str.format ではなく replace で
    必要なキーだけを差し替える（想定外の中括弧を壊さない）。

    例: fill_template(path, input=query, candidates=block)
        → テンプレ内の {input} / {candidates} をそれぞれ置換
    """
    with open(path, encoding="utf-8") as f:
        template = f.read()
    for key, value in fields.items():
        template = template.replace("{" + key + "}", value)
    return template
