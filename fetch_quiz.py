from pathlib import Path
import re


def normalize(text: str) -> str:
    """Нормализует текст: убирает лишние переносы строк, но сохраняет абзацы."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n\n", "<PARA>")
    text = re.sub(r"\n+", " ", text)
    text = text.replace("<PARA>", "\n\n")
    return text.strip()


def normalize_answer(answer: str) -> str:
    """Берём только первую часть ответа, до точки или скобок."""
    if not answer:
        return ""
    normalized = answer.strip().lower()
    normalized = normalized.replace("ё", "е")

    if "." in normalized:
        normalized = normalized.split(".", 1)[0]
    if "(" in normalized:
        normalized = normalized.split("(", 1)[0]
    
    normalized = re.sub(r"[«»\"'“”„`’‚,!?;:—–-]", " ", normalized)
    normalized = " ".join(normalized.split())
    return normalized


def load_quiz(dir_path: str | Path) -> dict[str, str]:
    """Загружает все .txt из папки и возвращает словарь {вопрос: ответ}."""
    dir_path = Path(dir_path)
    qa: dict[str, str] = {}

    for path in sorted(dir_path.glob("*.txt")):
        with open(path, "r", encoding="koi8-r") as f:
            text = f.read().replace("\r\n", "\n").replace("\r", "\n")

        question = None
        for block in text.split("\n\n"):
            block = normalize(block)
            if not block:
                continue

            if block.startswith("Вопрос"):
                question = block.split(":", 1)[1].strip() if ":" in block else block

            elif block.startswith("Ответ") and question:
                answer = block.split(":", 1)[1].strip() if ":" in block else block
                qa[question] = answer
                question = None

    return qa
