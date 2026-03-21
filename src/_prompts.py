from pathlib import Path


def load_prompt(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise RuntimeError("Missing prompt file: " + path) from None
