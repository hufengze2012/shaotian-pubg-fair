import json
import sys
import numpy as np
import pandas as pd
import requests
from typing import List, Dict, Any
from time import sleep
from time import monotonic


class PubgAPIError(Exception):
    pass


class PUBGAnalyzer:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        self.players = self.config['players']
        self.num_matches = self.config.get('num_matches', 100)
        self.request_timeout = self.config.get('request_timeout', 8)
        self.max_retries = self.config.get('max_retries', 3)
        self.target_recent_matches = self.config.get('target_recent_matches', self.num_matches)
        self.fetch_all_matches = self.config.get('fetch_all_matches', True)
        self.max_match_scan = self.config.get('max_match_scan', 30)
        self.recent_fetch_budget_seconds = self.config.get('recent_fetch_budget_seconds', 180)
        self.cache_path = self.config.get('cache_path', 'pubg_match_cache.json')
        self.lifetime_avg_kills: Dict[str, float] = {}
        self.lifetime_rounds: Dict[str, int] = {}
        self.match_cache = self._load_match_cache()

    def _load_match_cache(self) -> Dict[str, Any]:
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except FileNotFoundError:
            cache = {'version': 2, 'matches': {}}
        except json.JSONDecodeError:
            cache = {'version': 2, 'matches': {}}

        if not isinstance(cache, dict):
            cache = {'version': 2, 'matches': {}}

        # 兼容旧版本：按玩家存储 -> 按 match_id 存储
        if 'matches' not in cache and isinstance(cache.get('players'), dict):
            migrated_matches: Dict[str, Any] = {}
            for player_name, player_data in cache.get('players', {}).items():
                if not isinstance(player_data, dict):
                    continue
                player_matches = player_data.get('matches', {})
                if not isinstance(player_matches, dict):
                    continue
                for match_id, match_item in player_matches.items():
                    if not isinstance(match_item, dict):
                        continue
                    entry = migrated_matches.setdefault(match_id, {
                        'platform': str(player_data.get('platform', '')),
                        'created_at': str(match_item.get('created_at', '')),
                        'game_mode': str(match_item.get('game_mode', '')),
                        'players': {},
                        'usable': bool(match_item.get('usable', True))
                    })
                    if match_item.get('usable') is False:
                        entry['usable'] = False
                    if 'kills' in match_item:
                        entry['players'][player_name] = {'kills': int(match_item.get('kills', 0))}
            cache = {'version': 2, 'matches': migrated_matches}

        if 'matches' not in cache or not isinstance(cache['matches'], dict):
            cache['matches'] = {}
        cache['version'] = 2
        return cache

    def _save_match_cache(self) -> None:
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.match_cache, f, indent=2, ensure_ascii=False)

    def _get_recent_cached_kills(self, player_name: str, limit: int) -> List[int]:
        matches = self.match_cache.get('matches', {})
        if not isinstance(matches, dict) or not matches:
            return []

        valid_entries = []
        for item in matches.values():
            if not isinstance(item, dict):
                continue
            if item.get('usable') is False:
                continue
            players = item.get('players', {})
            if not isinstance(players, dict):
                continue
            player_item = players.get(player_name)
            if not isinstance(player_item, dict):
                continue
            valid_entries.append({
                'kills': int(player_item.get('kills', 0)),
                'created_at': str(item.get('created_at', ''))
            })

        valid_entries.sort(key=lambda x: x['created_at'], reverse=True)
        return [item['kills'] for item in valid_entries[:limit]]

    def _count_player_cached_matches(self, player_name: str) -> int:
        matches = self.match_cache.get('matches', {})
        if not isinstance(matches, dict):
            return 0
        count = 0
        for item in matches.values():
            if not isinstance(item, dict):
                continue
            players = item.get('players', {})
            if isinstance(players, dict) and player_name in players:
                count += 1
        return count

    def _request_json(self, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        last_err = None

        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, headers=headers, timeout=self.request_timeout)
            except requests.RequestException as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    sleep(1 + attempt)
                    continue
                raise PubgAPIError(f"请求失败: {url} | 错误: {e}") from e

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429 and attempt < self.max_retries - 1:
                retry_after = resp.headers.get('Retry-After')
                wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else (2 + attempt)
                print(f"⚠️ 命中限流，等待 {wait_seconds}s 后重试")
                sleep(wait_seconds)
                continue

            raise PubgAPIError(f"请求失败: {url} | 状态码: {resp.status_code} | 响应: {resp.text[:200]}")

        raise PubgAPIError(f"请求失败: {url} | 最后错误: {last_err}")

    def _extract_match_ids(self, player_obj: Dict[str, Any]) -> List[str]:
        relations = player_obj.get('relationships', {})
        matches = relations.get('matches', {}).get('data', [])
        return [m.get('id') for m in matches if m.get('type') == 'match' and m.get('id')]

    def _fetch_recent_squad_tpp_kills(
        self,
        platform: str,
        headers: Dict[str, str],
        player_name: str,
        match_ids: List[str]
    ) -> Dict[str, int]:
        allowed_modes = {'squad', 'normal-squad', 'squad-tpp'}
        scanned = 0
        max_scan = len(match_ids)
        target_matches = min(self.target_recent_matches, self.num_matches)
        start_ts = monotonic()
        new_saved = 0
        cache_hits = 0
        fetched_new_requests = 0
        backfill_requests = 0
        request_cap = len(match_ids) if self.fetch_all_matches else self.max_match_scan
        cached_matches = self.match_cache.setdefault('matches', {})
        print(f"    {player_name}: 开始抓取，最多发起 {request_cap} 个新请求，目标命中 {target_matches} 场 squad-tpp")

        for match_id in match_ids:
            if monotonic() - start_ts >= self.recent_fetch_budget_seconds:
                print(f"    {player_name}: 最近对局抓取达到时间上限 {self.recent_fetch_budget_seconds}s，提前结束")
                break

            scanned += 1
            cached_item = cached_matches.get(match_id)
            if cached_item is not None:
                cached_players = cached_item.get('players', {}) if isinstance(cached_item, dict) else {}
                if isinstance(cached_players, dict) and player_name in cached_players:
                    cache_hits += 1
                    if scanned % 5 == 0:
                        print(
                            f"    {player_name}: 已扫描 {scanned}/{max_scan} 场，缓存命中 {cache_hits} 场，"
                            f"新增有效 {new_saved} 场，补全请求 {backfill_requests} 次，新请求 {fetched_new_requests}"
                        )
                    continue
                backfill_requests += 1

            if fetched_new_requests >= request_cap:
                print(f"    {player_name}: 本轮新请求达到上限 {request_cap}，提前结束")
                break

            match_url = f"https://api.pubg.com/shards/{platform}/matches/{match_id}"
            try:
                match_data = self._request_json(match_url, headers)
            except PubgAPIError:
                fetched_new_requests += 1
                if scanned % 5 == 0:
                    print(
                        f"    {player_name}: 已扫描 {scanned}/{max_scan} 场，缓存命中 {cache_hits} 场，"
                        f"新增有效 {new_saved} 场，补全请求 {backfill_requests} 次，新请求 {fetched_new_requests}"
                    )
                continue

            game_mode = match_data.get('data', {}).get('attributes', {}).get('gameMode')
            created_at = str(match_data.get('data', {}).get('attributes', {}).get('createdAt', ''))
            participants = [
                item for item in match_data.get('included', [])
                if item.get('type') == 'participant'
            ]
            players_payload: Dict[str, Any] = {}
            for participant in participants:
                p_stats = participant.get('attributes', {}).get('stats', {})
                p_name = p_stats.get('name')
                if not p_name:
                    continue
                players_payload[p_name] = {
                    'kills': int(p_stats.get('kills', 0))
                }

            usable = game_mode in allowed_modes
            cached_matches[match_id] = {
                'platform': platform,
                'created_at': created_at,
                'game_mode': str(game_mode or ''),
                'usable': bool(usable),
                'players': players_payload
            }
            fetched_new_requests += 1

            if game_mode not in allowed_modes:
                if scanned % 5 == 0:
                    print(
                        f"    {player_name}: 已扫描 {scanned}/{max_scan} 场，缓存命中 {cache_hits} 场，"
                        f"新增有效 {new_saved} 场，补全请求 {backfill_requests} 次，新请求 {fetched_new_requests}"
                    )
                continue

            if player_name in players_payload:
                new_saved += 1

            if scanned % 5 == 0:
                print(
                    f"    {player_name}: 已扫描 {scanned}/{max_scan} 场，缓存命中 {cache_hits} 场，"
                    f"新增有效 {new_saved} 场，补全请求 {backfill_requests} 次，新请求 {fetched_new_requests}"
                )

            current_usable = len(self._get_recent_cached_kills(player_name, target_matches))
            if current_usable >= target_matches:
                print(f"    {player_name}: 已累计到 {current_usable} 场可用真实数据，达到目标")
                break

        print(
            f"    {player_name}: 抓取结束，扫描 {scanned} 场，缓存命中 {cache_hits} 场，"
            f"新增有效 {new_saved} 场，补全请求 {backfill_requests} 次，新请求 {fetched_new_requests}"
        )
        return {
            'scanned': scanned,
            'cache_hits': cache_hits,
            'new_saved': new_saved,
            'new_requests': fetched_new_requests,
            'backfill_requests': backfill_requests
        }

    def fetch_season_stats(self) -> Dict[str, List[int]]:
        """查询真实的 squad-tpp 对局击杀数据"""
        api_key = self.config.get('api_key')
        if not api_key or str(api_key).startswith('YOUR_'):
            raise PubgAPIError("未配置有效 API Key，无法查询真实数据")

        headers = {
            'Authorization': f"Bearer {api_key}",
            'Accept': 'application/vnd.api+json',
            'Accept-Encoding': 'gzip'
        }
        platform = self.config.get('platform', 'pc-as')
        names = [p['name'] for p in self.players]

        if len(names) > 10:
            raise PubgAPIError("players 查询单次最多支持 10 个玩家，请减少玩家数量")

        kills_data: Dict[str, List[int]] = {}
        print(f"🔄 查询 squad-tpp 真实数据: {names}")

        def lookup_players(shard: str):
            lookup_url = f"https://api.pubg.com/shards/{shard}/players?filter[playerNames]={','.join(names)}"
            lookup_data = self._request_json(lookup_url, headers)
            p_map: Dict[str, str] = {}
            p_match_ids: Dict[str, List[str]] = {}
            for item in lookup_data.get('data', []):
                name = item.get('attributes', {}).get('name')
                account_id = item.get('id')
                if not name or not account_id:
                    continue
                p_map[name] = account_id
                p_match_ids[name] = self._extract_match_ids(item)
            return p_map, p_match_ids

        effective_platform = platform
        player_map, player_match_ids = lookup_players(effective_platform)

        if platform.startswith('pc-') and player_match_ids and all(len(v) == 0 for v in player_match_ids.values()):
            print("  ⚠️ pc-as 返回的最近比赛为空，自动重试 steam 分片")
            steam_player_map, steam_match_ids = lookup_players('steam')
            if steam_player_map:
                effective_platform = 'steam'
                player_map = steam_player_map
                player_match_ids = steam_match_ids

        for name, account_id in player_map.items():
            print(f"  ✓ 找到 {name} → {account_id}，最近比赛ID: {len(player_match_ids.get(name, []))}")

        missing_names = [name for name in names if name not in player_map]
        if missing_names:
            raise PubgAPIError(f"以下玩家未找到: {missing_names}")

        for player in self.players:
            name = player['name']
            account_id = player_map[name]
            cached_before = self._count_player_cached_matches(name)

            stats_url = f"https://api.pubg.com/shards/{effective_platform}/players/{account_id}/seasons/lifetime"
            stats_data = self._request_json(stats_url, headers)
            attributes = stats_data.get('data', {}).get('attributes', {})

            game_modes = attributes.get('gameModeStats')
            if not isinstance(game_modes, dict):
                game_modes = attributes.get('stats', {}).get('gameModeStats', {})

            squad_stats = game_modes.get('squad') or game_modes.get('squad-tpp') or game_modes.get('normal-squad')
            if not squad_stats:
                raise PubgAPIError(f"{name} 没有 squad-tpp 统计，无法继续")

            rounds_played = int(squad_stats.get('roundsPlayed', 0))
            total_kills = int(squad_stats.get('kills', 0))
            avg = (total_kills / rounds_played) if rounds_played > 0 else 0.0
            self.lifetime_avg_kills[name] = avg
            self.lifetime_rounds[name] = rounds_played
            print(f"  ✓ {name}: squad-tpp 生涯均值 {avg:.2f} 击杀 ({rounds_played} 场)")

            match_ids = player_match_ids.get(name, [])
            if not match_ids:
                print(f"  ⚠️ {name}: 最近 14 天无可用比赛ID，仅使用生涯真实统计参与计算")
            else:
                progress = self._fetch_recent_squad_tpp_kills(effective_platform, headers, name, match_ids)
                print(
                    f"  ✓ {name}: 本次扫描 {progress['scanned']} 场，缓存命中 {progress['cache_hits']} 场，"
                    f"新增有效 {progress['new_saved']} 场，补全请求 {progress['backfill_requests']} 次，新请求 {progress['new_requests']} 次"
                )

            self._save_match_cache()
            cached_after = self._count_player_cached_matches(name)
            cached_kills = self._get_recent_cached_kills(name, self.num_matches)
            kills_data[name] = cached_kills

            if cached_kills:
                print(f"  ✓ {name}: 缓存累计 {cached_after} 场，可用于计算 {len(cached_kills)} 场最近真实数据")
            else:
                print(f"  ⚠️ {name}: 缓存可用对局为 0，仅使用生涯真实统计参与计算")
            if len(cached_kills) < self.num_matches:
                print(f"  ⚠️ {name}: 距离最近 {self.num_matches} 场还差 {self.num_matches - len(cached_kills)} 场，继续运行可增量补齐")

            if cached_after > cached_before:
                print(f"  ✓ {name}: 缓存增长 {cached_after - cached_before} 场（当前缓存文件: {self.cache_path}）")

            sleep(0.8)

        return kills_data

    def calculate_points(self, kills_data: Dict[str, List[int]]) -> Dict[str, float]:
        """按让分规则计算总分。"""
        return self.calculate_points_with_handicap(kills_data, {})

    def calculate_points_with_handicap(
        self,
        kills_data: Dict[str, List[int]],
        handicaps: Dict[str, float]
    ) -> Dict[str, float]:
        """按每场 max(0, 击杀-让分) 计算总分。"""
        points = {}
        n_players = len(self.players)
        for name, kills_list in kills_data.items():
            handicap = float(handicaps.get(name, 0.0))
            adjusted_kills = [max(0.0, float(k) - handicap) for k in kills_list]
            total_kills = sum(adjusted_kills)
            points_per_kill = 1 + (n_players - 1)
            points[name] = total_kills * points_per_kill
        return points

    def optimize_handicaps(self, kills_data: Dict[str, List[int]]) -> Dict:
        """让分规则：0.5 一档，仅允许减分，不允许加分。"""
        avgs = {}
        for name, kills in kills_data.items():
            if kills:
                avgs[name] = float(np.mean(kills))
            else:
                fallback_avg = self.lifetime_avg_kills.get(name)
                if fallback_avg is None:
                    raise PubgAPIError(f"{name} 没有最近对局数据且缺少生涯统计，无法计算让分")
                avgs[name] = float(fallback_avg)

        step = 0.5
        min_avg = min(avgs.values())

        def round_to_step(value: float, unit: float) -> float:
            return round(np.floor(value / unit + 0.5) * unit, 2)

        optimal_h = {}
        adjusted_avgs = {}
        for name, avg in avgs.items():
            raw_handicap = max(0.0, avg - min_avg)
            handicap = round_to_step(raw_handicap, step)
            adjusted_avg = max(0.0, avg - handicap)
            optimal_h[name] = handicap
            adjusted_avgs[name] = adjusted_avg

        final_var = float(np.var(list(adjusted_avgs.values())))
        return {
            'optimal_handicaps': optimal_h,
            'final_variance': final_var,
            'avg_kills': avgs,
            'adjusted_avg_kills': adjusted_avgs,
            'success': True,
            'step': step
        }

    def run_analysis(self):
        print("=== PUBG 让分策略分析 (基于 squad-tpp 真实对局) ===")

        kills_data = self.fetch_season_stats()
        opt_result = self.optimize_handicaps(kills_data)
        handicaps = opt_result['optimal_handicaps']
        points = self.calculate_points_with_handicap(kills_data, handicaps)

        avgs = {}
        for name, kills in kills_data.items():
            if kills:
                avgs[name] = float(np.mean(kills))
            else:
                avgs[name] = float(self.lifetime_avg_kills.get(name, 0.0))
        counts = {name: len(kills) for name, kills in kills_data.items()}
        adjusted_avgs = opt_result['adjusted_avg_kills']

        df = pd.DataFrame({
            'Player': list(avgs.keys()),
            'Match_Count': [counts[p] for p in avgs.keys()],
            'Avg_Kills_Before': [round(avgs[p], 2) for p in avgs.keys()],
            'Optimal_Handicap': list(opt_result['optimal_handicaps'].values()),
            'Avg_Kills_After': [round(adjusted_avgs[p], 2) for p in avgs.keys()],
            'Total_Points': [points[p] for p in avgs.keys()]
        })

        print("\n平均击杀 & 最优让分:")
        print(df.round(2))

        print("\n🎯 最合理的让分建议:")
        for p, h in opt_result['optimal_handicaps'].items():
            print(f"  {p}: {h:+.2f} 分")

        print(f"\n优化后方差: {opt_result['final_variance']:.4f} (越接近0越均衡)")

        print("\n说明:")
        print("- 仅使用真实 squad-tpp 对局数据")
        print("- 最近对局列表为空时，会回退为生涯真实统计（非模拟数据）")
        print("- 每名玩家可用对局数量受 PUBG 接口 14 天数据窗口影响")
        print("- 让分步进为 0.5，仅允许减分，不允许加分")
        print("- 每场有效击杀 = max(0, 本场击杀 - 让分)")
        print("- 示例：让分=1 时，本场击杀 1 记 0，击杀 0 也记 0")

        results = {
            'optimal_handicaps': opt_result['optimal_handicaps'],
            'avg_kills': opt_result['avg_kills'],
            'adjusted_avg_kills': opt_result['adjusted_avg_kills'],
            'analysis': df.to_dict('records'),
            'recent_kills_by_player': kills_data,
            'cache_file': self.cache_path,
            'rule': {
                'step': opt_result['step'],
                'only_deduction': True,
                'per_match_formula': 'max(0, kills - handicap)'
            }
        }

        with open('pubg_analysis_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        if 'Daisy_Six' in kills_data:
            daisy_kills = kills_data['Daisy_Six']
            print("\n=== Daisy_Six 最近对局击杀 (squad-tpp) ===")
            recent_10 = daisy_kills[:10]
            if recent_10:
                print("最近可用前10场:", recent_10)
                print(f"最近可用前10场总击杀: {sum(recent_10)} | 平均: {np.mean(recent_10):.2f}")
                print("\n=== Daisy_Six 可用对局统计 ===")
                print(f"对局数: {len(daisy_kills)} | 总击杀: {sum(daisy_kills)} | 平均: {np.mean(daisy_kills):.2f} | 最高: {max(daisy_kills)}")
            else:
                avg = self.lifetime_avg_kills.get('Daisy_Six', 0.0)
                rounds = self.lifetime_rounds.get('Daisy_Six', 0)
                print("最近 14 天没有可用 squad-tpp 对局")
                print(f"生涯真实统计: 平均击杀 {avg:.2f} | 场次 {rounds}")

            with open('kills_daisy_six.json', 'w', encoding='utf-8') as f:
                json.dump({
                    "player": "Daisy_Six",
                    "recent_10_kills": recent_10,
                    "kills_recent_available": daisy_kills,
                    "summary": {
                        "data_source": "recent_matches_or_lifetime_fallback",
                        "match_count": len(daisy_kills),
                        "total": sum(daisy_kills),
                        "average": round(float(np.mean(daisy_kills)), 2) if daisy_kills else round(float(self.lifetime_avg_kills.get('Daisy_Six', 0.0)), 2),
                        "max": int(max(daisy_kills)) if daisy_kills else 0,
                        "min": int(min(daisy_kills)) if daisy_kills else 0,
                        "lifetime_rounds": int(self.lifetime_rounds.get('Daisy_Six', 0)),
                        "lifetime_average": round(float(self.lifetime_avg_kills.get('Daisy_Six', 0.0)), 2),
                        "recent_10_avg": round(float(np.mean(recent_10)), 2) if recent_10 else 0.0
                    }
                }, f, indent=2, ensure_ascii=False)
            print("数据已保存到 kills_daisy_six.json")


if __name__ == "__main__":
    analyzer = PUBGAnalyzer()
    try:
        analyzer.run_analysis()
    except PubgAPIError as e:
        print(f"❌ 分析失败: {e}")
        sys.exit(1)
