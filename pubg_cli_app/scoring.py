from typing import Any, Dict, List

import numpy as np


STEP = 0.5


def evaluate_individual(
    records: List[Dict[str, Any]],
    player_names: List[str],
    handicaps: Dict[str, float],
) -> Dict[str, Any]:
    totals = {name: 0.0 for name in player_names}

    for rec in records:
        for name in player_names:
            raw_kill = float(rec["kills"][name])
            eff_kill = max(0.0, raw_kill - float(handicaps.get(name, 0.0)))
            totals[name] += eff_kill

    n = len(records)
    avgs = {name: (totals[name] / n if n > 0 else 0.0) for name in player_names}
    values = list(avgs.values())
    gap = (max(values) - min(values)) if values else 0.0
    var = float(np.var(values)) if values else 0.0

    return {"totals": totals, "avgs": avgs, "gap": gap, "var": var}


def evaluate_team(
    records: List[Dict[str, Any]],
    player_names: List[str],
    team_a: List[str],
    team_b: List[str],
    team_handicaps: Dict[str, float],
) -> Dict[str, Any]:
    totals = {name: 0.0 for name in player_names}

    h_a = float(team_handicaps.get("A", 0.0))
    h_b = float(team_handicaps.get("B", 0.0))

    for rec in records:
        a_kills = sum(float(rec["kills"][n]) for n in team_a)
        b_kills = sum(float(rec["kills"][n]) for n in team_b)

        a_eff = max(0.0, a_kills - h_a)
        b_eff = max(0.0, b_kills - h_b)
        diff = abs(a_eff - b_eff)

        if diff == 0:
            continue

        if a_eff > b_eff:
            for name in team_a:
                totals[name] += diff
            for name in team_b:
                totals[name] -= diff
        else:
            for name in team_b:
                totals[name] += diff
            for name in team_a:
                totals[name] -= diff

    n = len(records)
    avgs = {name: (totals[name] / n if n > 0 else 0.0) for name in player_names}
    values = list(avgs.values())
    gap = (max(values) - min(values)) if values else 0.0
    var = float(np.var(values)) if values else 0.0

    return {"totals": totals, "avgs": avgs, "gap": gap, "var": var}


def suggest_individual_handicaps(records: List[Dict[str, Any]], player_names: List[str]) -> Dict[str, Any]:
    handicaps = {name: 0.0 for name in player_names}
    best_eval = evaluate_individual(records, player_names, handicaps)

    for _ in range(200):
        improved = False
        for name in player_names:
            current = handicaps[name]
            candidates = [current + STEP]
            if current >= STEP:
                candidates.append(current - STEP)

            candidate_choice = None
            for val in candidates:
                trial = dict(handicaps)
                trial[name] = round(val, 2)
                ev = evaluate_individual(records, player_names, trial)
                score = (ev["var"], ev["gap"], sum(trial.values()))
                if candidate_choice is None or score < candidate_choice[0]:
                    candidate_choice = (score, trial, ev)

            if candidate_choice is None:
                continue

            _, trial, ev = candidate_choice
            cur_score = (best_eval["var"], best_eval["gap"], sum(handicaps.values()))
            new_score = (ev["var"], ev["gap"], sum(trial.values()))
            if new_score < cur_score:
                handicaps = trial
                best_eval = ev
                improved = True

        if not improved:
            break

    return {"handicaps": handicaps, "evaluation": best_eval}


def suggest_team_handicaps(
    records: List[Dict[str, Any]],
    player_names: List[str],
    team_a: List[str],
    team_b: List[str],
) -> Dict[str, Any]:
    if not records:
        h = {"A": 0.0, "B": 0.0}
        return {"handicaps": h, "evaluation": evaluate_team(records, player_names, team_a, team_b, h)}

    max_team_kills = 0.0
    for rec in records:
        a_kills = sum(float(rec["kills"][n]) for n in team_a)
        b_kills = sum(float(rec["kills"][n]) for n in team_b)
        max_team_kills = max(max_team_kills, a_kills, b_kills)

    upper = round(np.ceil((max_team_kills + 2.0) / STEP) * STEP, 2)
    grid = np.arange(0.0, upper + STEP / 2.0, STEP)

    best_tuple = None
    best_h = {"A": 0.0, "B": 0.0}
    best_eval = evaluate_team(records, player_names, team_a, team_b, best_h)

    for h_a in grid:
        for h_b in grid:
            h_a = round(float(h_a), 2)
            h_b = round(float(h_b), 2)
            if h_a > 0 and h_b > 0:
                continue
            h = {"A": h_a, "B": h_b}
            ev = evaluate_team(records, player_names, team_a, team_b, h)
            score_tuple = (ev["var"], ev["gap"], h_a + h_b, abs(h_a - h_b))
            if best_tuple is None or score_tuple < best_tuple:
                best_tuple = score_tuple
                best_h = h
                best_eval = ev

    return {"handicaps": best_h, "evaluation": best_eval}
