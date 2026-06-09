from __future__ import annotations

from pathlib import Path


def _rtf_escape(text: str) -> str:
    pieces: list[str] = []
    for char in text:
        codepoint = ord(char)
        if char == "\\":
            pieces.append(r"\\")
        elif char == "{":
            pieces.append(r"\{")
        elif char == "}":
            pieces.append(r"\}")
        elif char == "\n":
            pieces.append(r"\par ")
        elif codepoint <= 0x7F:
            pieces.append(char)
        else:
            pieces.append(rf"\u{codepoint}?")
    return "".join(pieces)


def generate_doc(title: str, content: str, output_path: Path) -> None:
    title_text = _rtf_escape(title or "Export")
    body_text = _rtf_escape(content or "")
    rtf = (
        r"{\rtf1\ansi\deff0"
        r"{\fonttbl{\f0\fnil\fcharset0 Microsoft YaHei;}}"
        r"\viewkind4\uc1\pard\f0\fs32 "
        f"{title_text}"
        r"\par\fs22 "
        f"{body_text}"
        r"\par}"
    )
    output_path.write_text(rtf, encoding="utf-8")

