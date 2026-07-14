"""OpenAI-compatible tool schemas for Ask the Lodge."""

from __future__ import annotations

_PERIOD_PROPERTIES = {
    "year": {
        "type": "integer",
        "description": "Optional calendar year filter.",
    },
    "month": {
        "type": "integer",
        "description": "Optional calendar month (1-12). Requires year.",
    },
    "period_preset": {
        "type": "string",
        "description": (
            "Optional named range: today, yesterday, last_7_days, "
            "last_weekend, or last_week. Same presets as the Games and "
            "Leaderboards Quick range filter."
        ),
    },
    "start_date": {
        "type": "string",
        "description": "Optional inclusive custom start date (YYYY-MM-DD).",
    },
    "end_date": {
        "type": "string",
        "description": "Optional inclusive custom end date (YYYY-MM-DD).",
    },
    "all_time": {
        "type": "boolean",
        "description": (
            "When true, ignore the Ask page default period and use all-time stats."
        ),
    },
}

ASK_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_game_types",
            "description": "List game types that have recorded games in this group.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_group_players",
            "description": (
                "List active players in the group with player_id, display_label, "
                "display_name, and username when linked. Use before query_player_detail "
                "when the question names players by first name or username."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_leaderboard",
            "description": "Current leaderboard rankings for one game type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {
                        "type": "string",
                        "description": "Game type code, e.g. dominos or mahjongg.",
                    },
                    **_PERIOD_PROPERTIES,
                    "game_size": {
                        "type": "integer",
                        "description": "Optional player count filter (2, 3, 4, etc.).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return (default 10).",
                    },
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_placement_leaders",
            "description": (
                "Players who finish in a given placement most often. "
                "Placement is 0-indexed: 0=1st, 1=2nd, 2=3rd."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    "placement": {
                        "type": "integer",
                        "description": "0 for 1st place, 1 for 2nd place, etc.",
                    },
                    **_PERIOD_PROPERTIES,
                    "game_size": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": ["game_type_code", "placement"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_month_leaders",
            "description": (
                "Leaders for a calendar month, optionally filtered by year. "
                "Use month=12 for December / holiday season questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    "month": {
                        "type": "integer",
                        "description": "Calendar month 1-12.",
                    },
                    "year": {
                        "type": "integer",
                        "description": "Optional year. Omit to aggregate the month across all years.",
                    },
                    "game_size": {"type": "integer"},
                    "metric": {
                        "type": "string",
                        "enum": ["rank_score", "wins", "games_played"],
                    },
                    "limit": {"type": "integer"},
                },
                "required": ["game_type_code", "month"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_rank_trends",
            "description": (
                "Compare each player's rank score in a recent window vs the prior window "
                "to find who is improving or declining."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    "days": {
                        "type": "integer",
                        "description": "Length of each comparison window in days (default 90).",
                    },
                    "game_size": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_player_detail",
            "description": (
                "Detailed stats for one player in one game type, including placement "
                "mix, best/worst score, date range, podium count, and tie count. "
                "Use player_query for names (first name, display label, username) "
                "or player_id from list_group_players / the roster."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "player_id": {"type": "integer"},
                    "player_query": {
                        "type": "string",
                        "description": (
                            "Player name or username from the question, e.g. Nancy, "
                            "David, or nmanpearl."
                        ),
                    },
                    "game_type_code": {"type": "string"},
                    **_PERIOD_PROPERTIES,
                    "game_size": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_head_to_head",
            "description": (
                "Head-to-head stats for two players in games they both attended: "
                "games together, wins, ties, and losses when the game type supports them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    "player_a_id": {"type": "integer"},
                    "player_a_query": {
                        "type": "string",
                        "description": "First player name or username from the roster.",
                    },
                    "player_b_id": {"type": "integer"},
                    "player_b_query": {
                        "type": "string",
                        "description": "Second player name or username from the roster.",
                    },
                    **_PERIOD_PROPERTIES,
                    "game_size": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_hall_of_fame",
            "description": (
                "Period leaders across years or months, like the Hall of Fame grid. "
                "Use for dynasty questions and repeat winners."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "granularity": {
                        "type": "string",
                        "enum": ["year", "month"],
                        "description": "year for annual leaders, month for monthly leaders.",
                    },
                    "game_type_code": {
                        "type": "string",
                        "description": "Optional filter to one game type.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max period rows to return (default 10).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_loss_leaders",
            "description": (
                "Players with the most recorded losses for one game type. "
                "Only meaningful when the game type tracks explicit losses "
                "(e.g. Progressive Rummy)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    **_PERIOD_PROPERTIES,
                    "game_size": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_players",
            "description": (
                "Side-by-side stats for 2 to 5 players in one game type. "
                "Prefer this over multiple query_player_detail calls when "
                "comparing several players."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    "player_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "2 to 5 player_id values from the roster.",
                    },
                    "player_queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "2 to 5 player names or usernames when player_id "
                            "is not known."
                        ),
                    },
                    **_PERIOD_PROPERTIES,
                    "game_size": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_date_range_leaderboard",
            "description": (
                "Leaderboard for games played in a date span (inclusive). "
                "Prefer period_preset for today, yesterday, last_7_days, "
                "last_weekend, or last_week. Otherwise pass start_date and end_date."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    "period_preset": {
                        "type": "string",
                        "description": (
                            "Named range: today, yesterday, last_7_days, "
                            "last_weekend, or last_week."
                        ),
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Inclusive start date (YYYY-MM-DD).",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Inclusive end date (YYYY-MM-DD).",
                    },
                    "game_size": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_location_leaderboard",
            "description": (
                "Leaderboard for games at one venue or location. "
                "Use location_query for names like Joe's house."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    "location_id": {"type": "integer"},
                    "location_query": {
                        "type": "string",
                        "description": "Location name from the group's saved venues.",
                    },
                    **_PERIOD_PROPERTIES,
                    "game_size": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_team_pairings",
            "description": (
                "Observed two-player teams (duo sides) and individual rankings for "
                "one game type. Use for best partner, best duo, or team pairing "
                "questions. Returns observed_duo_teams with member labels, "
                "rank_score, wins_display, and games_played."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    **_PERIOD_PROPERTIES,
                    "game_size": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
]
