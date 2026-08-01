"""Curated Ask the Lodge example questions for the Examples UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from django.utils.text import slugify

Reliability = Literal["supported", "partial", "not_supported"]


@dataclass(frozen=True)
class AskToolCall:
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class AskExample:
    slug: str
    category: str
    questions: tuple[str, ...]
    reliability: Reliability
    tool_calls: tuple[AskToolCall, ...]
    game_type_code: str = "dominos"
    limitation: str = ""
    typical_tool_rounds: str = "1"
    try_it_enabled: bool = True

    @property
    def reliability_label(self) -> str:
        return {
            "supported": "Supported",
            "partial": "Partial",
            "not_supported": "Not supported",
        }[self.reliability]

    @property
    def primary_question(self) -> str:
        return self.questions[0] if self.questions else ""

    @property
    def can_try_it(self) -> bool:
        return self.try_it_enabled and bool(self.primary_question)


def build_try_it_ask_url(*, demo_group_id: int, example: AskExample) -> str:
    from urllib.parse import urlencode

    from django.urls import reverse

    params = {
        "group": demo_group_id,
        "game_type_code": example.game_type_code,
        "question": example.primary_question,
    }
    return f"{reverse('insights:ask')}?{urlencode(params)}"


def resolve_try_it_demo_group():
    from leaderlodge.groups.demo import DEMO_GROUP_NAME
    from leaderlodge.groups.models import Group
    from leaderlodge.groups.services import get_demo_group

    demo = get_demo_group()
    if demo is not None:
        return demo
    return Group.objects.filter(name=DEMO_GROUP_NAME).order_by("pk").first()


def try_it_url_for_example(example: AskExample) -> str | None:
    if not example.can_try_it:
        return None
    demo = resolve_try_it_demo_group()
    if demo is None:
        return None
    return build_try_it_ask_url(demo_group_id=demo.pk, example=example)


def try_it_urls_by_slug() -> dict[str, str]:
    demo = resolve_try_it_demo_group()
    if demo is None:
        return {}
    return {
        example.slug: build_try_it_ask_url(demo_group_id=demo.pk, example=example)
        for example in ASK_EXAMPLES
        if example.can_try_it
    }


def _example(
    category: str,
    questions: str | tuple[str, ...],
    *,
    reliability: Reliability,
    game_type_code: str = "dominos",
    tool_calls: tuple[AskToolCall, ...] = (),
    limitation: str = "",
    typical_tool_rounds: str = "1",
    try_it_enabled: bool = True,
) -> AskExample:
    if isinstance(questions, str):
        parts = (questions.strip(),)
    else:
        parts = tuple(part.strip() for part in questions if part.strip())
    return AskExample(
        slug=slugify(category),
        category=category,
        questions=parts,
        reliability=reliability,
        tool_calls=tool_calls,
        game_type_code=game_type_code,
        limitation=limitation.strip(),
        typical_tool_rounds=typical_tool_rounds,
        try_it_enabled=try_it_enabled,
    )


ASK_EXAMPLES: tuple[AskExample, ...] = (
    _example(
        "Current standings",
        "Who leads dominos all time?",
        reliability="supported",
        tool_calls=(AskToolCall("query_leaderboard", {"all_time": True}),),
    ),
    _example(
        "Period standings",
        ("Who was on top in 2025?", "March 2026 leaderboard"),
        reliability="supported",
        tool_calls=(
            AskToolCall("query_leaderboard", {"year": 2025}),
            AskToolCall(
                "query_leaderboard",
                {"year": 2026, "month": 3},
                note="Use year and month from the question.",
            ),
        ),
        typical_tool_rounds="1",
    ),
    _example(
        "Field-size standings",
        "Who leads 4-player mahjongg?",
        reliability="supported",
        game_type_code="mahjongg",
        tool_calls=(AskToolCall("query_leaderboard", {"game_size": 4}),),
    ),
    _example(
        "Placement frequency",
        "Who finishes 2nd most in dominos?",
        reliability="supported",
        tool_calls=(AskToolCall("query_placement_leaders", {"placement": 1}),),
        typical_tool_rounds="1",
    ),
    _example(
        "Placement + period",
        "Who got 2nd place most in January 2026?",
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_placement_leaders",
                {"placement": 1, "month": 1, "year": 2026},
            ),
        ),
    ),
    _example(
        "Placement + month (all years)",
        "Who gets 2nd most every January?",
        reliability="supported",
        tool_calls=(
            AskToolCall("query_placement_leaders", {"placement": 1, "month": 1}),
        ),
    ),
    _example(
        "Monthly leaders",
        "Who wins most in December?",
        reliability="supported",
        tool_calls=(
            AskToolCall("query_month_leaders", {"month": 12, "metric": "wins"}),
        ),
    ),
    _example(
        "Monthly rank score",
        "Best rank score in June 2025",
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_month_leaders",
                {"year": 2025, "month": 6, "metric": "rank_score"},
            ),
        ),
    ),
    _example(
        "Trends",
        "Who is improving most in the last quarter?",
        reliability="supported",
        tool_calls=(AskToolCall("query_rank_trends", {"days": 90}),),
    ),
    _example(
        "Player snapshot",
        "How is Amelia doing in dominos?",
        reliability="supported",
        tool_calls=(AskToolCall("query_player_detail", {"player_query": "Amelia"}),),
    ),
    _example(
        "Player placement mix",
        "What place does Hudson finish most often?",
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_player_detail",
                {"player_query": "Hudson"},
                note="Read placements from the result.",
            ),
        ),
    ),
    _example(
        "Score highlights",
        "What was Amelia's best dominos score?",
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_player_detail",
                {"player_query": "Amelia"},
                note="Read best_score and worst_score.",
            ),
        ),
    ),
    _example(
        "Player dates and podiums",
        ("When did Amelia last play?", "How often does she podium?"),
        reliability="supported",
        tool_calls=(AskToolCall("query_player_detail", {"player_query": "Amelia"}),),
    ),
    _example(
        "Head-to-head",
        "Who wins more when Amelia and Hudson play together?",
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_head_to_head",
                {"player_a_query": "Amelia", "player_b_query": "Hudson"},
            ),
        ),
        typical_tool_rounds="1 to 2",
    ),
    _example(
        "Head-to-head (alt phrasing)",
        "Amelia vs Hudson: who wins when they share a table?",
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_head_to_head",
                {"player_a_query": "Amelia", "player_b_query": "Hudson"},
            ),
        ),
        typical_tool_rounds="1 to 2",
    ),
    _example(
        "Team pairings",
        (
            "Which players would make the best two-person team in pickleball?",
            "Who is the strongest duo in pickleball?",
        ),
        reliability="supported",
        game_type_code="pickleball",
        tool_calls=(AskToolCall("query_team_pairings"),),
        limitation=(
            "Answers use recorded two-player sides only (e.g. Amelia+Harper), "
            "not name-based guesses."
        ),
    ),
    _example(
        "Rally pickleball standings",
        ("Who is best at rally?", "Who leads rally scoring in pickleball?"),
        reliability="supported",
        game_type_code="pickleball",
        tool_calls=(
            AskToolCall(
                "query_leaderboard",
                {"score_type": "rally", "all_time": True},
            ),
        ),
    ),
    _example(
        "Pickleball pickled (winner)",
        (
            "Who pickled the most opponents?",
            "Who wins the most shutout games in pickleball?",
        ),
        reliability="supported",
        game_type_code="pickleball",
        tool_calls=(
            AskToolCall(
                "query_leaderboard",
                {"shutout_only": True, "all_time": True},
            ),
        ),
        limitation=(
            "Pickled here means the winning side shut out every opponent. "
            "Rank by wins with shutout_only=true."
        ),
    ),
    _example(
        "Got pickled (loser)",
        (
            "Who got pickled the most?",
            "Who was pickled the most in pickleball?",
        ),
        reliability="not_supported",
        game_type_code="pickleball",
        limitation="Loser-side got-pickled counts are not tracked. Ask can only answer winner-side pickled (shutout wins).",
        try_it_enabled=True,
    ),
    _example(
        "Double dominos standings",
        (
            "Who wins the most double games in dominos?",
            "Who leads dominos double games?",
        ),
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_leaderboard",
                {"double_game": True, "all_time": True},
            ),
        ),
    ),
    _example(
        "Half-game Progressive Rummy",
        (
            "Who is the worst half-game player?",
            "Who struggles most in half games?",
        ),
        reliability="supported",
        game_type_code="progressiverummy",
        tool_calls=(
            AskToolCall(
                "query_leaderboard",
                {"half_game": True, "all_time": True, "limit": 10},
                note="Sort by rank; last row is worst standing in scope.",
            ),
        ),
    ),
    _example(
        "Hall of Fame / dynasty",
        ("Who dominated across years?", "Repeat monthly winners?"),
        reliability="supported",
        tool_calls=(
            AskToolCall("query_hall_of_fame", {"granularity": "year"}),
            AskToolCall("query_hall_of_fame", {"granularity": "month"}),
        ),
    ),
    _example(
        "Period winners by game",
        "Who won 2024 in each game?",
        reliability="supported",
        tool_calls=(AskToolCall("query_hall_of_fame", {"granularity": "year"}),),
    ),
    _example(
        "Roster discovery",
        "Who is in our group?",
        reliability="supported",
        tool_calls=(AskToolCall("list_group_players"),),
    ),
    _example(
        "Name-based grouping",
        ("Do boys or girls play better?", "Do men or women play better?"),
        reliability="supported",
        tool_calls=(
            AskToolCall("list_group_players"),
            AskToolCall(
                "query_player_detail",
                note="One call per classified player, or compare_players for small sets.",
            ),
        ),
        typical_tool_rounds="2 to 5",
    ),
    _example(
        "Game types",
        "What games do we track?",
        reliability="supported",
        tool_calls=(AskToolCall("list_game_types"),),
    ),
    _example(
        "Two-player career compare",
        "How do Amelia and Hudson stack up in dominos?",
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "compare_players",
                {"player_queries": ["Amelia", "Hudson"]},
            ),
            AskToolCall(
                "query_head_to_head",
                {"player_a_query": "Amelia", "player_b_query": "Hudson"},
                note="Optional for shared-table stats.",
            ),
        ),
        typical_tool_rounds="1 to 2",
    ),
    _example(
        "Multi-year rank compare",
        (
            "Which years was David ahead of Nancy in dominos?",
            "How many years has Amelia led Hudson in dominos?",
        ),
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_player_rank_history",
                {"player_queries": ["David", "Nancy"]},
                note="Omit years to cover every year with recorded games.",
            ),
        ),
    ),
    _example(
        "Multi-player compare",
        "Compare Aurora, Lucas, and Lily in Progressive Rummy",
        reliability="supported",
        game_type_code="progressiverummy",
        tool_calls=(
            AskToolCall(
                "compare_players",
                {"player_queries": ["Aurora", "Lucas", "Lily"]},
            ),
        ),
    ),
    _example(
        "Loss leaders",
        "Who loses most in Progressive Rummy?",
        reliability="supported",
        game_type_code="progressiverummy",
        tool_calls=(AskToolCall("query_loss_leaders"),),
    ),
    _example(
        "Custom date span",
        ("Who led dominos during spring break?", "Leaders from Spring Break week"),
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_date_range_leaderboard",
                {
                    "start_date": "YYYY-MM-DD",
                    "end_date": "YYYY-MM-DD",
                },
                note="Model infers dates from the question.",
            ),
        ),
    ),
    _example(
        "Venue leaders",
        "Who leads at Home?",
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_location_leaderboard",
                {"location_query": "Home"},
            ),
        ),
    ),
    _example(
        "City leaders",
        ("Who plays best in Santa Monica?", "Who leads in Los Angeles?"),
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_region_leaderboard",
                {"city": "Santa Monica"},
            ),
        ),
        limitation=(
            "Only venues with city filled are included. "
            "Sparse geo coverage may omit many games."
        ),
    ),
    _example(
        "State leaders",
        ("Who plays best in California?", "Who leads in CA?"),
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_region_leaderboard",
                {"state": "California"},
            ),
        ),
        limitation=(
            "Only venues with state filled are included. "
            "US state names normalize to two-letter codes."
        ),
    ),
    _example(
        "Outside a state",
        ("Who plays best outside of California?", "Who leads outside CA?"),
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_region_leaderboard",
                {"state": "California", "exclude": True},
            ),
        ),
        limitation=(
            "Only venues with a non-matching state filled are included. "
            "Venues with blank state are omitted."
        ),
    ),
    _example(
        "Where we play most",
        ("Where do we play most?", "Which venues have the most games?"),
        reliability="supported",
        tool_calls=(AskToolCall("query_play_locations", {}),),
    ),
    _example(
        "Player games by state",
        (
            "Show me the list of states in which Nancy has played and her number of games in each.",
            "Where has David played by state?",
        ),
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_player_play_locations",
                {"player_query": "Nancy", "group_by": "state"},
            ),
        ),
        limitation=(
            "Blank or missing state is returned as an unknown bucket. "
            "Do not treat unknown games as California or any other state."
        ),
    ),
    _example(
        "Specific game",
        "What happened in the game on 3/15/2026?",
        reliability="supported",
        tool_calls=(
            AskToolCall(
                "query_game_detail",
                {"played_on": "2026-03-15"},
                note="Model infers date from the question.",
            ),
        ),
    ),
    _example(
        "Current leader profile",
        ("Tell me about the leader", "Who is on top?"),
        reliability="supported",
        tool_calls=(
            AskToolCall("query_leaderboard", {"limit": 1}),
            AskToolCall(
                "query_player_detail",
                {"player_id": "from leaderboard rank 1"},
            ),
        ),
        typical_tool_rounds="2",
    ),
    _example(
        "UI period vs question intent",
        'Ask filter set to "2025" but question says "all time"',
        reliability="partial",
        limitation="Model may omit all_time: true despite prompt guidance.",
        typical_tool_rounds="1",
        try_it_enabled=False,
    ),
    _example(
        "Placement without field size",
        '"Who finishes last?" in groups that mix 3- and 5-player games',
        reliability="partial",
        limitation="Last placement index depends on game_size.",
        tool_calls=(
            AskToolCall(
                "query_placement_leaders",
                note="Pass game_size when the question implies a field size.",
            ),
        ),
    ),
    _example(
        "Multi-tool chains",
        "Compare dominos and mahjongg leaders, then who improves faster",
        reliability="partial",
        limitation="May exceed 5 tool rounds if the model chains one tool per round.",
        typical_tool_rounds="3 to 5",
    ),
    _example(
        "Name-based group compares",
        (
            "Boys vs girls average rank",
            "Men vs women average rank for large rosters",
        ),
        reliability="partial",
        limitation=(
            "Many query_player_detail or compare_players calls; may hit round limits. "
            "meta.coverage flags when stats were fetched for fewer than 60% of roster players."
        ),
        typical_tool_rounds="3 to 5",
    ),
    _example(
        "Inactive players",
        "How did former member Alex do?",
        reliability="partial",
        limitation="Active roster only.",
    ),
    _example(
        "Sparse trends",
        "Who improved most this month?",
        reliability="partial",
        limitation="Trend tool needs games in both comparison windows.",
        tool_calls=(AskToolCall("query_rank_trends", {"days": 30}),),
    ),
    _example(
        "Ambiguous names",
        "How is Lucas doing? with two Lucases in the group",
        reliability="partial",
        limitation="Ambiguity error or wrong match.",
        tool_calls=(AskToolCall("query_player_detail", {"player_query": "Lucas"}),),
    ),
    _example(
        '"Most" without metric',
        "Who is the best in dominos?",
        reliability="partial",
        limitation="Model must choose rank_score vs wins vs placement.",
        tool_calls=(AskToolCall("query_leaderboard"),),
    ),
    _example(
        "Exact counts across many players",
        "Rank everyone by 2nd-place finishes",
        reliability="partial",
        limitation="20-row cap per tool.",
        tool_calls=(AskToolCall("query_placement_leaders", {"placement": 1}),),
    ),
    _example(
        "Three or more players together",
        "Stats when Amelia, Hudson, and Lucas play together",
        reliability="partial",
        limitation=(
            "Head-to-head is two-player only; compare_players is career stats, "
            "not shared-table only."
        ),
    ),
    _example(
        "Streaks",
        "Longest win streak?",
        reliability="not_supported",
        limitation="Not computed in any Ask tool.",
    ),
    _example(
        "Rank movement after one game",
        "Who did Amelia pass when she won last Tuesday?",
        reliability="not_supported",
        limitation="Matchup page only.",
    ),
    _example(
        "Cross game type summary",
        "Who is best across all our games?",
        reliability="not_supported",
        limitation="No multi-type aggregate tool.",
    ),
    _example(
        "Predictions",
        "Who will win next month?",
        reliability="not_supported",
        limitation="Prompt forbids; no predictive data.",
    ),
)

_ASK_EXAMPLES_BY_SLUG = {example.slug: example for example in ASK_EXAMPLES}


def list_ask_examples() -> list[AskExample]:
    return list(ASK_EXAMPLES)


def get_ask_example(slug: str) -> AskExample | None:
    return _ASK_EXAMPLES_BY_SLUG.get(slug)


def group_ask_examples_by_reliability() -> dict[Reliability, list[AskExample]]:
    grouped: dict[Reliability, list[AskExample]] = {
        "supported": [],
        "partial": [],
        "not_supported": [],
    }
    for example in ASK_EXAMPLES:
        grouped[example.reliability].append(example)
    return grouped
