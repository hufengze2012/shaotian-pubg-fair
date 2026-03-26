import os
import sys


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


def use_color() -> bool:
    return os.getenv("NO_COLOR") is None and sys.stdout.isatty()


def paint(text: str, color: str = "", bold: bool = False) -> str:
    if not use_color():
        return text
    prefix = ""
    if bold:
        prefix += ANSI.BOLD
    if color:
        prefix += color
    return f"{prefix}{text}{ANSI.RESET}"


def title(text: str) -> str:
    return paint(text, ANSI.CYAN, bold=True)


def success(text: str) -> str:
    return paint(text, ANSI.GREEN, bold=True)


def warn(text: str) -> str:
    return paint(text, ANSI.YELLOW, bold=True)


def error(text: str) -> str:
    return paint(text, ANSI.RED, bold=True)


def accent(text: str) -> str:
    return paint(text, ANSI.MAGENTA, bold=True)
