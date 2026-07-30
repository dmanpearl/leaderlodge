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

_GAME_FEATURE_PROPERTIES = {
    "score_type": {
        "type": "string",
        "description": (
            "Pickleball only. traditional or rally. Call list_game_types for "
            "features and ask_aliases when the user says normal or rally scoring."
        ),
    },
    "double_game": {
        "type": "boolean",
        "description": (
            "Dominos only. true for double games (winner scored 60+), false "
            "for regular. Call list_game_types for ask_aliases like double or normal."
        ),
    },
    "half_game": {
        "type": "boolean",
        "description": (
            "Progressive Rummy only. true for half games, false for full. "
            "Call list_game_types for ask_aliases."
        ),
    },
    "shutout_only": {
        "type": "boolean",
        "description": (
            "When true, only shutout games (one winner, every opponent scored 0). "
            "Use for active winner questions: who pickled, shut out, or won shutout "
            "games. Rank by wins. Not for got pickled / was pickled (loser side; "
            "not tracked). See list_game_types shutout metadata."
        ),
    },
}

ASK_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_game_types",
            "description": (
                "List game types that have recorded games in this group. Each "
                "type includes features (score_type, double_game, half_game) "
                "with value codes and ask_aliases for natural-language filters. "
                "Types that support shutouts also include a shutout object "
                "with ask_aliases (e.g. pickle, shutout)."
            ),
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
                    **_GAME_FEATURE_PROPERTIES,
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
                    **_GAME_FEATURE_PROPERTIES,
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
                    **_GAME_FEATURE_PROPERTIES,
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_player_play_locations",
            "description": (
                "One player's games grouped by state, city, or venue. "
                "Use for lists like which states Nancy has played in and "
                "how many games in each. Always report the unknown/blank "
                "geo bucket when present; never invent that all games are "
                "in one state from query_player_detail totals alone."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "player_id": {"type": "integer"},
                    "player_query": {
                        "type": "string",
                        "description": ("Player name or username from the question."),
                    },
                    "game_type_code": {"type": "string"},
                    "group_by": {
                        "type": "string",
                        "enum": ["state", "city", "venue"],
                        "description": (
                            "state for per-state counts, city for per-city, "
                            "venue for per-location. Default state."
                        ),
                    },
                    **_PERIOD_PROPERTIES,
                    "game_size": {"type": "integer"},
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return (default 20).",
                    },
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
                    **_GAME_FEATURE_PROPERTIES,
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
                    **_GAME_FEATURE_PROPERTIES,
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
                    **_GAME_FEATURE_PROPERTIES,
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
                    **_GAME_FEATURE_PROPERTIES,
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
                "Leaderboard for games at one named venue only "
                "(e.g. Joe's house, Home). Do NOT use for city or state "
                "questions; use query_region_leaderboard instead."
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
                    **_GAME_FEATURE_PROPERTIES,
                    "limit": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_region_leaderboard",
            "description": (
                "Leaderboard for games across venues in a city and/or state. "
                "Use for who plays best in Santa Monica or California. "
                "For outside California / outside a city, pass the same "
                "city/state with exclude=true. Pass US state as full name or "
                "two-letter code. Requires city/state on saved venues; check "
                "coverage_thin."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. Santa Monica.",
                    },
                    "state": {
                        "type": "string",
                        "description": (
                            "State or region, e.g. California or CA. "
                            "US full names are normalized to two-letter codes."
                        ),
                    },
                    "exclude": {
                        "type": "boolean",
                        "description": (
                            "When true, rank games at venues outside the "
                            "given city/state (venues with blank city/state "
                            "are omitted). Use for outside California."
                        ),
                    },
                    **_PERIOD_PROPERTIES,
                    "game_size": {"type": "integer"},
                    **_GAME_FEATURE_PROPERTIES,
                    "limit": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_play_locations",
            "description": (
                "Venues ranked by how many games were played there. "
                "Optional city and/or state limit the set; exclude=true "
                "selects venues outside that region. Use for "
                "where do we play most questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "game_type_code": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "exclude": {
                        "type": "boolean",
                        "description": (
                            "When true with city/state, only venues outside "
                            "that region (blank city/state omitted)."
                        ),
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
                    **_GAME_FEATURE_PROPERTIES,
                    "limit": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
]
