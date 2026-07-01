from __future__ import annotations


def _format_stat_count(value: float) -> str:
    rounded = round(float(value), 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return str(rounded)


def format_count_with_pct(count: float, pct: float) -> str:
    return f"{_format_stat_count(count)} ({pct}%)"


def format_pct_with_count_of_total(count: float, pct: float, total: float) -> str:
    return f"{pct}% ({_format_stat_count(count)} of {_format_stat_count(total)})"


def format_total_with_avg_per_game(total: float, games: float) -> str:
    avg = _avg_points_per_game(total, games)
    return f"{_format_points_total(total)} ({_format_stat_count(avg)}/game)"


def format_avg_per_game_with_total(total: float, games: float) -> str:
    avg = _avg_points_per_game(total, games)
    return f"{_format_stat_count(avg)}/game ({_format_points_total(total)} total)"


def _avg_points_per_game(total: float, games: float) -> float:
    if games <= 0:
        return 0.0
    return round(float(total) / float(games), 1)


def _format_points_total(value: float) -> str:
    return f"{int(round(float(value))):,}"


def add_points_display_fields(payload: dict) -> dict:
    if "total_points" not in payload or "games_played" not in payload:
        return payload
    total = float(payload["total_points"] or 0)
    games = float(payload["games_played"] or 0)
    payload["avg_points_per_game"] = _avg_points_per_game(total, games)
    payload["total_points_display"] = format_total_with_avg_per_game(total, games)
    payload["total_points_display_alt"] = format_avg_per_game_with_total(total, games)
    return payload


def add_avg_score_display_fields(payload: dict) -> dict:
    average_score = payload.get("average_score")
    if average_score is None:
        return payload
    avg = round(float(average_score), 1)
    payload["avg_points_per_game"] = avg
    payload["avg_points_display"] = f"{_format_stat_count(avg)}/game"
    return payload


def add_outcome_display_fields(
    payload: dict,
    *,
    total: float,
    outcomes: tuple[tuple[str, str, str], ...] = (
        ("wins", "win_pct", "wins_display"),
        ("losses", "loss_pct", "losses_display"),
        ("ties", "tie_pct", "ties_display"),
    ),
) -> dict:
    for count_key, pct_key, display_key in outcomes:
        if count_key not in payload or pct_key not in payload:
            continue
        count = float(payload[count_key] or 0)
        pct = float(payload[pct_key] or 0)
        payload[display_key] = format_count_with_pct(count, pct)
        payload[f"{display_key}_alt"] = format_pct_with_count_of_total(
            count, pct, total
        )
    return payload
