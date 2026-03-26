import re
from typing import Any, Dict, List, Tuple

from pubg_cli_app.console import ANSI, accent, error, paint, success, title, warn


def _parse_index_list(text: str) -> List[int]:
    parts = [p for p in re.split(r"[\s,，]+", text.strip()) if p]
    return [int(p) for p in parts]


def _is_valid_half_step(value: float) -> bool:
    return abs(value / 0.5 - round(value / 0.5)) < 1e-9


def print_score_table(table_title: str, player_names: List[str], evaluation: Dict[str, Any]) -> None:
    print(f"\n{accent(table_title)}")
    print(paint("-" * len(table_title), ANSI.MAGENTA))
    print(paint(f"{'玩家':<15}{'总分':>10}{'均分':>10}", ANSI.BLUE, bold=True))
    for name in player_names:
        total = float(evaluation["totals"][name])
        avg = float(evaluation["avgs"][name])
        print(f"{name:<15}{total:>10.2f}{avg:>10.2f}")
    print(paint(f"分差(max-min): {float(evaluation['gap']):.2f}", ANSI.YELLOW, bold=True))
    print(paint(f"方差: {float(evaluation['var']):.4f}", ANSI.CYAN, bold=True))


def print_profile_table(names: List[str], profile: Dict[str, Dict[str, float]]) -> None:
    table_title = "历史击杀画像"
    print(f"\n{title(table_title)}")
    print(paint("-" * len(table_title), ANSI.CYAN))
    header = (
        f"{'玩家':<15}"
        f"{'全局平均击杀':>14}"
        f"{'四人同局平均击杀':>18}"
        f"{'四人同局场次':>14}"
    )
    print(paint(header, ANSI.BLUE, bold=True))

    for name in names:
        row = profile[name]
        print(
            f"{name:<15}"
            f"{float(row['global_avg']):>14.2f}"
            f"{float(row['together_avg']):>18.2f}"
            f"{int(row['together_count']):>14d}"
        )


def prompt_selected_players(all_names: List[str]) -> List[str]:
    print(f"\n{title('可选玩家')}: ")
    for idx, name in enumerate(all_names, start=1):
        print(f"  {idx}. {name}")

    while True:
        raw = input("\n请输入4个参赛编号（如: 1 2 3 4）: ")
        try:
            indices = _parse_index_list(raw)
        except ValueError:
            print(error("输入无效，请输入数字编号"))
            continue

        if len(indices) != 4:
            print(warn("必须且仅能输入4个编号"))
            continue
        if len(set(indices)) != 4:
            print(warn("编号不能重复"))
            continue
        if any(i < 1 or i > len(all_names) for i in indices):
            print(warn("编号超出范围"))
            continue

        return [all_names[i - 1] for i in indices]


def prompt_mode() -> int:
    print(f"\n{title('请选择模式')}: ")
    print("  1. 个人")
    print("  2. 组队")
    while True:
        raw = input("输入模式编号: ").strip()
        if raw in {"1", "2"}:
            return int(raw)
        print(warn("模式输入无效，请输入 1 或 2"))


def prompt_team(selected_names: List[str]) -> Tuple[List[str], List[str]]:
    print(f"\n{title('当前4名参赛者')}: ")
    for idx, name in enumerate(selected_names, start=1):
        print(f"  {idx}. {name}")
    print("输入A队的2名编号，例如: 1 3（则B队自动为2 4）")

    while True:
        raw = input("A队成员编号: ")
        try:
            picks = _parse_index_list(raw)
        except ValueError:
            print(error("输入无效，请输入数字编号"))
            continue

        if len(picks) != 2:
            print(warn("A队必须输入2个编号"))
            continue
        if len(set(picks)) != 2:
            print(warn("A队编号不能重复"))
            continue
        if any(i < 1 or i > 4 for i in picks):
            print(warn("编号必须在1~4"))
            continue

        team_a = [selected_names[picks[0] - 1], selected_names[picks[1] - 1]]
        team_b = [name for name in selected_names if name not in team_a]
        return team_a, team_b


def _prompt_non_negative_half_step(prompt: str) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            val = float(raw)
        except ValueError:
            print(error("输入无效，请输入数字"))
            continue

        if val < 0:
            print(warn("让分必须 >= 0"))
            continue
        if not _is_valid_half_step(val):
            print(warn("让分必须是 0.5 的倍数，例如 0 / 0.5 / 1 / 1.5"))
            continue

        return round(val, 2)


def prompt_individual_handicaps(selected_names: List[str]) -> Dict[str, float]:
    print(f"\n{title('请输入个人让分（0.5步进，且>=0）')}")
    result: Dict[str, float] = {}
    for name in selected_names:
        result[name] = _prompt_non_negative_half_step(f"  {name} 让分: ")
    return result


def prompt_team_handicaps(team_a: List[str], team_b: List[str]) -> Dict[str, float]:
    print(f"\n{title('请输入队伍让分（0.5步进，且>=0，且只能单边让分）')}")
    print(f"  A队: {team_a[0]} / {team_a[1]}")
    print(f"  B队: {team_b[0]} / {team_b[1]}")

    while True:
        h_a = _prompt_non_negative_half_step("  A队让分: ")
        h_b = _prompt_non_negative_half_step("  B队让分: ")
        if not (h_a > 0 and h_b > 0):
            return {"A": h_a, "B": h_b}
        print(warn("规则限制：A队和B队不能同时 > 0，请重新输入（例如 A=3, B=0）"))


def print_recommend_individual(handicaps: Dict[str, float], names: List[str]) -> None:
    print(f"\n{success('建议让分（个人）')}: ")
    for name in names:
        h = float(handicaps.get(name, 0.0))
        print(f"  {paint(name, ANSI.BLUE, bold=True)}: {paint(f'{h:.2f}', ANSI.GREEN, bold=True)}")


def print_recommend_team(handicaps: Dict[str, float]) -> None:
    print(
        f"\n{success(f'建议让分（队伍）: A队 {float(handicaps.get('A', 0.0)):.2f}, B队 {float(handicaps.get('B', 0.0)):.2f}')}")
