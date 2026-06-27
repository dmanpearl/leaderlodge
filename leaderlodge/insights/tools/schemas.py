"""OpenAI-compatible tool schemas for Ask the Lodge."""

from __future__ import annotations

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
                    "year": {
                        "type": "integer",
                        "description": "Optional calendar year filter.",
                    },
                    "month": {
                        "type": "integer",
                        "description": "Optional calendar month (1-12). Requires year.",
                    },
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
                    "year": {"type": "integer"},
                    "month": {"type": "integer"},
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
                "Detailed stats for one player in one game type. "
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
                    "year": {"type": "integer"},
                    "month": {"type": "integer"},
                    "game_size": {"type": "integer"},
                },
                "required": ["game_type_code"],
            },
        },
    },
]
