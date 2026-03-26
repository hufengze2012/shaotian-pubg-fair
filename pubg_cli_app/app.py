from typing import List

from pubg_cli_app.api import PubgAPIError, PubgClient
from pubg_cli_app.cache import MatchCache
from pubg_cli_app.config import AppConfig
from pubg_cli_app.console import accent, error, success, title, warn
from pubg_cli_app.history import build_kill_profile, load_common_records, refresh_common_history
from pubg_cli_app.scoring import (
    evaluate_individual,
    evaluate_team,
    suggest_individual_handicaps,
    suggest_team_handicaps,
)
from pubg_cli_app.ui import (
    print_profile_table,
    print_recommend_individual,
    print_recommend_team,
    print_score_table,
    prompt_individual_handicaps,
    prompt_mode,
    prompt_selected_players,
    prompt_team,
    prompt_team_handicaps,
)


def run_cli(config: AppConfig, no_refresh: bool = False) -> int:
    player_names = [p.name for p in config.players]

    print(title("PUBG 历史均分结算 CLI"))
    selected_names = prompt_selected_players(player_names)
    mode = prompt_mode()

    cache = MatchCache(config.cache_path)

    stats = None
    if not no_refresh:
        client = PubgClient(
            api_key=config.api_key,
            timeout=config.request_timeout,
            max_retries=config.max_retries,
        )
        try:
            stats = refresh_common_history(
                client=client,
                cache=cache,
                platform=config.platform,
                names=selected_names,
            )
            print(success(
                f"\n数据刷新完成: 分片={stats.shard}, 四人同局候选={stats.common_candidates}, "
                f"缓存命中={stats.cache_hits}, 新拉取={stats.detail_requests}"
            ))
        except PubgAPIError as exc:
            print(warn(f"\n在线刷新失败，回退到本地 CLI 缓存: {exc}"))

    common_records = load_common_records(cache, selected_names, config.num_matches)
    if not common_records:
        if stats is not None and stats.common_candidates == 0:
            print(warn("\n诊断: 当前四人交集为 0，明细如下"))
            for name in selected_names:
                print(
                    warn(
                        f"  {name}: 最近比赛列表 {stats.player_match_counts.get(name, 0)} 场"
                    )
                )
            if stats.pair_overlaps:
                print(warn("  两两同局重合场次:"))
                for pair_name, overlap in sorted(stats.pair_overlaps.items()):
                    print(warn(f"    {pair_name}: {overlap} 场"))
        print(error("\n没有找到这4个人同局的历史数据。请检查玩家选择或先确保网络可用再重试。"))
        return 1

    print(success(f"\n四人同局样本场次: {len(common_records)}"))
    if len(common_records) < config.num_matches:
        print(warn(f"样本少于目标 {config.num_matches} 场，当前按可用样本计算"))

    profile = build_kill_profile(cache, selected_names, common_records)
    print_profile_table(selected_names, profile)

    if mode == 1:
        manual_handicaps = prompt_individual_handicaps(selected_names)
        manual_eval = evaluate_individual(common_records, selected_names, manual_handicaps)
        print_score_table("个人模式 - 当前让分结果", selected_names, manual_eval)

        suggestion = suggest_individual_handicaps(common_records, selected_names)
        print_recommend_individual(suggestion["handicaps"], selected_names)
        print_score_table("个人模式 - 建议让分结果", selected_names, suggestion["evaluation"])
        return 0

    team_a, team_b = prompt_team(selected_names)
    print(success(f"\n分队结果: A队={team_a[0]}/{team_a[1]}, B队={team_b[0]}/{team_b[1]}"))

    manual_team_h = prompt_team_handicaps(team_a, team_b)
    manual_eval = evaluate_team(common_records, selected_names, team_a, team_b, manual_team_h)
    print(accent(f"\n当前队伍让分: A队 {manual_team_h['A']:.2f}, B队 {manual_team_h['B']:.2f}"))
    print_score_table("组队模式 - 当前让分结果", selected_names, manual_eval)

    suggestion = suggest_team_handicaps(common_records, selected_names, team_a, team_b)
    print_recommend_team(suggestion["handicaps"])
    print_score_table("组队模式 - 建议让分结果", selected_names, suggestion["evaluation"])
    return 0
