import os
import re

from ..config import config


def strip_images(text: str) -> str:
    """画像リンク ![alt](url) を除去する（埋め込みに寄与しないため）。"""
    return re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)


def strip_code_blocks(text: str) -> str:
    """コードブロック（``` ～ ```）を除去する。ベクトル化用テキストを作るときだけ使う。"""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def split_into_sections(markdown_text: str):
    """Markdown を見出し単位のセクションに分ける（一次分割）。

    ### を基本の区切りにし、無ければ ## で区切る。H1 はタイトル扱いで区切らない。
    コードブロック内の "#" は見出しとみなさない。
    戻り値: [{"heading_path": [...], "body": "..."}, ...]
    """
    lines = markdown_text.splitlines()

    in_code_block = False
    current_headings = ["", "", "", "", "", ""]  # 直近の H1〜H6（index 0 = H1）

    sections = []
    current_body_lines = []
    current_path = []

    def flush():
        body = "\n".join(current_body_lines).strip()
        if body:
            sections.append({"heading_path": list(current_path), "body": body})

    for line in lines:
        if line.lstrip().startswith("```"):
            in_code_block = not in_code_block
            current_body_lines.append(line)
            continue

        heading_match = None
        if not in_code_block:
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)

        # H2 / H3 を新セクションの開始とみなす（H1 は区切りに使わない）
        if heading_match and len(heading_match.group(1)) in (2, 3):
            flush()
            current_body_lines = []

        if heading_match:
            level = len(heading_match.group(1))
            current_headings[level - 1] = heading_match.group(2).strip()
            for deeper in range(level, 6):  # 深いレベルはリセット
                current_headings[deeper] = ""
            current_path = [h for h in current_headings if h]

        current_body_lines.append(line)

    flush()
    return sections


def split_by_paragraph_keeping_code(body: str):
    """上限超のセクションを段落（空行）で再分割する（二次分割）。コードは途中で割らない。"""
    blocks = []
    in_code = False
    buf = []
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            buf.append(line)
            if in_code:
                blocks.append(("code", "\n".join(buf)))
                buf = []
            in_code = not in_code
            continue
        buf.append(line)
    if buf:
        blocks.append(("text", "\n".join(buf)))

    chunks = []
    current = ""

    def push():
        if current.strip():
            chunks.append(current.strip())

    for kind, text in blocks:
        if kind == "text":
            for para in re.split(r"\n\s*\n", text):
                para = para.strip()
                if not para:
                    continue
                candidate = (current + "\n\n" + para).strip() if current else para
                if len(candidate) > config.CHUNK_MAX_TOKENS and current:
                    push()
                    current = para
                else:
                    current = candidate
        else:
            candidate = (current + "\n\n" + text).strip() if current else text
            if len(candidate) > config.CHUNK_MAX_TOKENS and current:
                push()
                current = text
            else:
                current = candidate

    push()
    return chunks

def chunk_markdown_file(path: str):
    """1 ファイルをチャンク化する。各チャンクは 2 種のテキストを持つ。

      content    : 本文（コード込み）。結果表示・Claude の矛盾判定に使う
      embed_text : 本文（コード除去）。これだけをベクトル化する
    """
    file_name = os.path.basename(path)

    with open(path, encoding="utf-8") as f:
        raw = f.read()

    # 画像リンク ![alt](url) を除去する
    raw = strip_images(raw)

    # Markdown を見出し単位のセクションに分割する
    sections = split_into_sections(raw)

    chunks = []
    for section in sections:
        body = section["body"]

        if len(body) <= config.CHUNK_MAX_TOKENS:
            pieces = [body]
        else:
            pieces = split_by_paragraph_keeping_code(body)

        for piece in pieces:
            content = piece
            embed_text = strip_code_blocks(piece).strip()
            chunks.append({
                "content": content,
                "embed_text": embed_text,
                "file": file_name,
                "heading_path": section["heading_path"],
            })

    return chunks
