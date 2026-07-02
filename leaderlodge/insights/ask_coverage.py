"""Detect when Ask tool results may not cover the full roster."""

from __future__ import annotations

import re
from typing import Any

_WHOLE_ROSTER_QUESTION = re.compile(
    r"\b("
    r"boys?\s+and\s+girls?|"
    r"boys?\s+or\s+girls?|"
    r"men\s+and\s+women|"
    r"men\s+or\s+women|"
    r"all players|"
    r"everyone|"
    r"each player|"
    r"whole group|"
    r"group members?|"
    r"our group|"
    r"who plays better"
    r")\b",
    re.IGNORECASE,
)


def _player_id_from_args(arguments: dict[str, Any], *, prefix: str = "") -> int | None:
    id_key = f"{prefix}id" if prefix else "player_id"
    raw = arguments.get(id_key)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def analyze_ask_tool_coverage(
    *,
    tool_rounds: list[dict[str, Any]],
    roster_player_count: int,
    question: str,
) -> dict[str, Any]:
    """Summarize how many roster players were covered by Ask tool calls."""
    player_ids: set[int] = set()
    roster_from_tools: int | None = None
    leaderboard_rows = 0
    rounds_with_calls = 0

    for round_data in tool_rounds:
        calls = round_data.get("calls") or []
        if calls:
            rounds_with_calls += 1
        for call in calls:
            tool_name = str(call.get("tool") or "")
            arguments = call.get("arguments") or {}
            result = call.get("result") or {}

            if tool_name == "query_player_detail":
                player_id = _player_id_from_args(arguments)
                if player_id is not None:
                    player_ids.add(player_id)
                elif isinstance(result.get("player_id"), int):
                    player_ids.add(result["player_id"])
            elif tool_name == "query_head_to_head":
                for prefix in ("player_a_", "player_b_"):
                    player_id = _player_id_from_args(arguments, prefix=prefix)
                    if player_id is not None:
                        player_ids.add(player_id)
            elif tool_name == "query_leaderboard":
                rankings = result.get("rankings") or []
                leaderboard_rows = max(leaderboard_rows, len(rankings))
            elif tool_name == "list_group_players":
                players = result.get("players") or []
                roster_from_tools = len(players)

    roster_players = roster_from_tools or roster_player_count
    players_with_stats_fetched = max(len(player_ids), leaderboard_rows)
    whole_roster_question = bool(_WHOLE_ROSTER_QUESTION.search(question))

    reasons: list[str] = []
    likely_incomplete = False

    if roster_players >= 5 and whole_roster_question:
        if players_with_stats_fetched == 0:
            likely_incomplete = True
            reasons.append(
                "no per-player or leaderboard stats were fetched for a group-wide question"
            )
        elif players_with_stats_fetched < roster_players:
            threshold = max(3, int(roster_players * 0.6))
            if players_with_stats_fetched < threshold:
                likely_incomplete = True
                reasons.append(
                    f"stats were fetched for {players_with_stats_fetched} of "
                    f"{roster_players} roster players"
                )

    return {
        "roster_players": roster_players,
        "players_with_stats_fetched": players_with_stats_fetched,
        "player_detail_calls": len(player_ids),
        "leaderboard_rows_fetched": leaderboard_rows,
        "tool_rounds_with_calls": rounds_with_calls,
        "likely_incomplete": likely_incomplete,
        "reasons": reasons,
    }


def append_incomplete_data_note(markdown: str, coverage: dict[str, Any]) -> str:
    if not coverage.get("likely_incomplete"):
        return markdown
    reasons = coverage.get("reasons") or []
    detail = reasons[0] if reasons else "not all roster players were queried"
    note = (
        f"\n\n*Note: This answer may be based on incomplete data ({detail}). "
        "Try Regenerate if the comparison looks too narrow.*"
    )
    if note.strip() in markdown:
        return markdown
    return f"{markdown.rstrip()}{note}"
