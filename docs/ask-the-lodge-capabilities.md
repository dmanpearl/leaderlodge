# Ask the Lodge: capability audit and expansion plan

> **Companion:** [ai-insights.md](./ai-insights.md) (shipped surfaces, API contract, UX, env, testing). This document tracks what Ask can answer, tool limits, and planned expansion.

**Last reviewed:** 2026-08-01

---

## How Ask works (constraints that affect every answer)

| Constraint | Value | Effect |
| ---------- | ----- | ------ |
| Tool rounds | Up to 5 (`ASK_MAX_TOOL_ROUNDS` in `router.py`) | Each round is one LLM call; the model may request **multiple tools in parallel** within a round. Sequential one-tool-per-round chains (e.g. compare two players plus head-to-head) can exhaust the cap. |
| Row limit | 1 to 20 per tool (`ToolExecutor.MAX_LIMIT`) | "Everyone in the group" questions truncate |
| Rankings | Python ORM only | The model never computes `rank_score`, placement counts, or trends |
| Scope | One group per request | No cross-group comparisons |
| Default period | Ask page filters (`year` / `month` / `period_preset` / `start_date` / `end_date` on `POST /insights/ask/query/`) | When a tool omits period fields, the UI-selected period applies. Same resolver as Games and Leaderboards. |
| All-time override | `all_time: true` on period-aware tools | Ignores the Ask page default period |
| Player roster | Active players only, embedded in the user message | Inactive or historical players may not resolve |
| Question player hints | Server resolves usernames and `vs` segments before the LLM runs | Lists `player_id` for each mention; executor binds queries even with quotes |
| Placement index | 0 = 1st, 1 = 2nd, 2 = 3rd in tool args | The model must translate "2nd place" to `placement=1` |
| Score direction | `score_direction` on game-type tool results (`low_wins` or `high_wins`) | Applies to **raw game points only** (Progressive Rummy: lower points are better). Does **not** apply to `rank_score` |
| Rank score | Always higher-is-better, every game type | `rank_score` and `rank` follow LeaderLodge standings; never invert for `low_wins` |
| Scoring note | `scoring_note` on low-wins game types | Reminder that raw points invert usual meaning; explicitly excludes `rank_score` |
| Outcome display | `wins_display`, `losses_display`, `ties_display` (and `*_display_alt`) | Python-formatted strings such as `81 (25.1%)` or `25.1% (81 of 323)`; Ask cites these for comparisons |
| Points display | `total_points_display`, `avg_points_display` (and `total_points_display_alt`) | Per-game average required for comparisons: e.g. `136,100 (404.4/game)` or `404.4/game` |
| Debug | `include_debug: true` on any insight POST | Returns `tool_rounds`, `available_tools`, full LLM message chain |

---

## Shared tool response fields

Many game-type tools include:

| Field | When present | Meaning |
| ----- | ------------ | ------- |
| `score_direction` | Game-type scoped tools | `low_wins` (Progressive Rummy) or `high_wins` (dominos, mahjongg, etc.) |
| `scoring_note` | `low_wins` only | Raw game points only; lower points are better. `rank_score` remains higher-is-better |
| `all_time` | Request param on period-aware tools | Omits Ask page default period filter |

Player outcome fields (`query_player_detail`, `query_head_to_head` player rows):

| Field | Example | Meaning |
| ----- | ------- | ------- |
| `wins_display` | `81 (25.1%)` | Preferred citation format for comparisons |
| `wins_display_alt` | `25.1% (81 of 323)` | Alternate pct-first format |
| `losses_display`, `ties_display` | Same pattern | Loss and tie rates with counts |
| `win_pct`, `loss_pct`, `tie_pct` | Raw numbers | Used to build display fields; prefer `*_display` in answers |

Built by `leaderlodge/insights/tools/rate_display.py` and `scoring_interpretation_note()` in `games/registry.py`.

### Ask answer formatting (prompt-driven)

| Situation | Expected style |
| --------- | -------------- |
| Two-player compare | Prose paragraphs only; no per-player bullet stat blocks |
| Overall rank | **Required first** for any player comparison: rank number and rank_score for each player |
| Win/loss/tie rates | Quote `wins_display`, `losses_display`, `ties_display` verbatim |
| Scoring volume | Quote `total_points_display` or `avg_points_display`; compare average points per game, not raw totals |
| Same `games_played` | Raw win/loss counts without percentages are acceptable |
| Progressive Rummy / `low_wins` | Lower raw game points are better; `rank_score` is still higher-is-better |
| General answers | 2 to 4 short paragraphs or up to 5 bullet points |

Models differ in how they batch tool calls: some issue one tool per round (uses the round cap faster) while others parallelize (e.g. head-to-head plus two player details in one round). If Ask fails with "exceeded the tool call limit," retry with `refresh: true` or inspect `debug.tool_rounds`.

---

## Ask tool catalog

### `list_game_types`

No parameters. Returns game type codes that have at least one recorded game in the group. Each entry includes `code`, `name`, and `score_direction`.

### `list_group_players`

No parameters. Returns active roster: `player_id`, `display_label`, `display_name`, optional `username`, `first_name`, `last_name`.

### `query_leaderboard`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | Must exist in group |
| `year`, `month` | No | Calendar period; omit both to use Ask default period |
| `all_time` | No | When true, ignore Ask page default period |
| `game_size` | No | Filter by player count (2, 3, 4, 5, ...) |
| `limit` | No | Default 10, max 20 |

Returns ranked rows: `rank`, `rank_score`, `games_played`, `wins`, `win_pct`, plus `score_direction`.

### `query_placement_leaders`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `placement` | Yes | 0-indexed: 0 = 1st, 1 = 2nd, ... max 9 |
| `year`, `month`, `all_time` | No | Same period resolution as leaderboard |
| `game_size` | No | Strongly affects meaning for "2nd place" in N-player games |
| `limit` | No | Default 10, max 20 |

Returns players ordered by **weighted count** of finishes at that placement.

**Important:** This answers "who finishes in this placement most often," not "who had the highest rank score in January." For monthly rank leaders, use `query_month_leaders`.

### `query_month_leaders`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `month` | Yes | 1 to 12 |
| `year` | No | If set: leaders for that calendar month in that year. If omitted: aggregate the same month across all years |
| `game_size` | No | |
| `metric` | No | `rank_score` (default), `wins`, or `games_played` |
| `limit` | No | Default 10, max 20 |

### `query_rank_trends`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `days` | No | 7 to 365, default 90 |
| `game_size` | No | |
| `limit` | No | Sorted by `improvement` (recent minus prior rank score) |

Skips players with zero weighted games in either window.

### `query_player_detail`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `player_id` or `player_query` | One of | Server-side name matching |
| `year`, `month`, `all_time`, `game_size` | No | Period and field-size filters |

Returns rank stats, placement breakdown, score highlights, dates, podium stats, and outcome display fields (`wins_display`, `losses_display`, `ties_display`, plus `*_display_alt`). Includes `losses`, `loss_pct`, `ties`, `tie_pct`. Adds `scoring_note` when `score_direction` is `low_wins`.

### `query_head_to_head`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `player_a_id` or `player_a_query` | One of | First player |
| `player_b_id` or `player_b_query` | One of | Second player |
| `year`, `month`, `all_time` | No | Period filter on shared games |
| `game_size` | No | Optional player-count filter |

Returns `games_together`, `score_direction`, optional `scoring_note`, and per-player stats for games **both players attended** (including games with other players at the table): overall `rank` and `rank_score`, `games_played`, `wins`, `win_pct`, `wins_display`, `ties`, `losses`, `total_points`, `total_points_display`, `avg_points_per_game`, `max_score`, `min_score`, and matching `*_display` / `*_pct` fields.

### `query_hall_of_fame`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `granularity` | No | `year` (default) or `month` |
| `game_type_code` | No | Filter to one game type |
| `limit` | No | Max period rows, default 10, max 20 |

Returns period leaders like the Hall of Fame grid: `period_label`, leader `display_label`, `rank_score` per game type.

### `query_loss_leaders`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `year`, `month`, `all_time` | No | Same period resolution as leaderboard |
| `game_size` | No | |
| `limit` | No | Default 10, max 20 |

Returns players ordered by recorded **losses** (weighted count). Only meaningful when the game type tracks explicit losses (Progressive Rummy). Other game types return `supports_loser: false` and an error hint; use `query_placement_leaders` for last-place frequency.

### `compare_players`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `player_ids` or `player_queries` | One of | 2 to 5 players |
| `year`, `month`, `all_time`, `game_size` | No | Period and field-size filters |

Returns one JSON payload with a `players` array of `query_player_detail` snapshots (rank, outcomes, scores, display fields). Saves tool rounds vs multiple `query_player_detail` calls.

### `query_player_rank_history`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `player_ids` or `player_queries` | One of | 2 to 5 players |
| `years` | No | List of calendar years, e.g. `[2023, 2024, 2025]`. Omit to cover every year with recorded games (max 15) |
| `game_size` | No | |

Returns one row per year (`history`) with each player's `rank`, `rank_score`, `games_played`, and `has_games`, plus a `leader` (player_id and display_label) when exactly one of the given players has the best rank that year. `leader` is `null` and `tied: true` when the given players share the best rank that year, and `null` with `tied: false` when fewer than two of them have recorded games that year. Use this instead of one `query_player_detail` or `compare_players` call per year; it answers "which years was X ahead of Y" in a single tool round.

### `query_team_pairings`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | Team games such as pickleball |
| `year`, `month`, `all_time` | No | Same period resolution as leaderboard |
| `game_size` | No | |
| `limit` | No | Default 10, max 20 |

Returns `observed_duo_teams` (recorded two-player sides with `member_labels`, `rank_score`, `wins_display`, and `games_played`) plus `individual_rankings` for context. Use for best partner, best duo, or team pairing questions. The model must not recommend pairs from names or stereotypes when this tool is available.

### `query_date_range_leaderboard`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `period_preset` | No | `today`, `yesterday`, `last_7_days`, `last_weekend`, or `last_week` (same Quick range as Games / Leaderboards) |
| `start_date`, `end_date` | No* | Inclusive dates (`YYYY-MM-DD`). Required together when `period_preset` is omitted |
| `game_size` | No | |
| `limit` | No | Default 10, max 20 |

Returns ranked rows for games played in the date span. Vesting is not applied (same as calendar period filters).

### `query_location_leaderboard`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `location_id` or `location_query` | One of | Venue from the group's location library (name only, not city/state) |
| `year`, `month`, `all_time` | No | Period filter |
| `game_size` | No | |
| `limit` | No | Default 10, max 20 |

Returns ranked rows for games at that location, plus `location_name`.

### `query_region_leaderboard`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `city` and/or `state` | At least one | City is case-insensitive. US state full names normalize to two-letter codes (e.g. California to CA). `city` may be `"Santa Monica, CA"`. |
| `exclude` | No | When true, rank venues outside the given city/state (blank city/state omitted). Use for "outside California". |
| `year`, `month`, `all_time` | No | Period filter |
| `game_size` | No | |
| `limit` | No | Default 10, max 20 |

Returns ranked rows for games at all matched venues, plus `matched_venues`, `region_label`, `exclude`, and coverage fields (`coverage_thin`, optional `coverage_note`). Only venues with matching (or, when `exclude`, non-matching) city/state fields are included; ungeocoded venues are omitted.

### `query_play_locations`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `city` / `state` | No | Optional region filter (same rules as `query_region_leaderboard`) |
| `year`, `month`, `all_time` | No | Period filter |
| `game_size` | No | |
| `limit` | No | Default 10, max 20 |

Returns venues ordered by `games_played`, with city/state when present.

### `query_player_play_locations`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `player_id` or `player_query` | One of | Same resolution as `query_player_detail` |
| `group_by` | No | `state` (default), `city`, or `venue` |
| `year`, `month`, `all_time` | No | Period filter |
| `game_size` | No | |
| `limit` | No | Default 20, max 20 |

Returns `rows` of counts for that player, plus `total_games`, `games_unknown_region`, and optional `coverage_note`. Blank or missing geo is an explicit unknown bucket; do not treat those games as belonging to a specific state.

### `query_game_detail`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `played_on` | Yes | Game date (`YYYY-MM-DD`); model infers from natural-language questions |
| `game_size` | No | Disambiguate when multiple games share a date |

Returns scores, placements, location, and players for one recorded game.

---

## Capability matrix

### Supported (reliable when the model picks the right tool and args)

| Category | Example questions | Tool(s) |
| -------- | ----------------- | ------- |
| Current standings | "Who leads dominos all time?" | `query_leaderboard` + `all_time: true` |
| Period standings | "Who was on top in 2025?" / "March 2026 leaderboard" | `query_leaderboard` with `year` / `month` |
| Field-size standings | "Who leads 4-player mahjongg?" | `query_leaderboard` + `game_size` |
| Placement frequency | "Who finishes 2nd most in dominos?" | `query_placement_leaders`, `placement=1` |
| Placement + period | "Who got 2nd place most in January 2026?" | `query_placement_leaders`, `placement=1`, `month=1`, `year=2026` |
| Placement + month (all years) | "Who gets 2nd most every January?" | `query_placement_leaders`, `placement=1`, `month=1` |
| Monthly leaders | "Who wins most in December?" | `query_month_leaders`, `month=12`, `metric=wins` |
| Monthly rank score | "Best rank score in June 2025" | `query_month_leaders`, `year=2025`, `month=6` |
| Trends | "Who is improving most in the last quarter?" | `query_rank_trends`, `days=90` |
| Player snapshot | "How is Amelia doing in dominos?" | `query_player_detail`, `player_query` |
| Player placement mix | "What place does Hudson finish most often?" | `query_player_detail` (read `placements`) |
| Score highlights | "What was Amelia's best dominos score?" | `query_player_detail` (`best_score`, `worst_score`) |
| Player dates and podiums | "When did Amelia last play?" / "How often does she podium?" | `query_player_detail` |
| Head-to-head | "Who wins more when Amelia and Hudson play together?" | `query_head_to_head` |
| Head-to-head (alt phrasing) | "Amelia vs Hudson: who wins when they share a table?" | `query_head_to_head` |
| Team pairings | "Which players would make the best two-person team in pickleball?" | `query_team_pairings` |
| Hall of Fame / dynasty | "Who dominated across years?" / "Repeat monthly winners?" | `query_hall_of_fame` |
| Period winners by game | "Who won 2024 in each game?" | `query_hall_of_fame`, `granularity=year` |
| Roster discovery | "Who is in our group?" | `list_group_players` |
| Name-based grouping | "Do boys or girls play better?" / "Do men or women play better?" / classify by first name | `list_group_players` + model name knowledge + per-player or leaderboard tools for stats |
| Game types | "What games do we track?" | `list_game_types` |
| Two-player career compare | "How do Amelia and Hudson stack up in dominos?" | Two `query_player_detail` calls, `query_head_to_head`, or `compare_players` |
| Multi-year rank compare | "Which years was David ahead of Nancy in dominos?" | `query_player_rank_history` (one call covers every year) |
| Multi-player compare | "Compare Aurora, Lucas, and Lily in Progressive Rummy" | `compare_players` (2 to 5 players) |
| Loss leaders | "Who loses most in Progressive Rummy?" | `query_loss_leaders` |
| Custom date span | "Who led dominos during spring break?" / "Leaders from Spring Break week" | `query_date_range_leaderboard` with `start_date` / `end_date` (model infers dates from the question) |
| Venue leaders | "Who leads at Home?" | `query_location_leaderboard` with `location_query` |
| City / state leaders | "Who plays best in Santa Monica?" / "Who leads in California?" | `query_region_leaderboard` with `city` and/or `state` |
| Outside a region | "Who plays best outside of California?" | `query_region_leaderboard` with `state` and `exclude: true` |
| Where we play most | "Where do we play most?" | `query_play_locations` |
| Player games by state/city/venue | "Which states has Nancy played in?" | `query_player_play_locations` with `group_by` |
| Specific game | "What happened in the game on 3/15/2026?" | `query_game_detail` with `played_on` (model infers date from the question) |
| Current leader profile | "Tell me about the leader" / "Who is on top?" | `query_leaderboard` (limit 1), then `query_player_detail` for rank 1 |

### Partial or unreliable

| Category | Example questions | Why unreliable |
| -------- | ----------------- | -------------- |
| UI period vs question intent | Ask filter set to "2025" but question says "all time" | Model may omit `all_time: true` despite prompt guidance |
| Placement without field size | "Who finishes last?" in groups that mix 3- and 5-player games | Last placement index depends on `game_size` |
| Multi-tool chains | "Compare dominos and mahjongg leaders, then who improves faster" | May exceed 5 rounds if the model chains one tool per round |
| Name-based group compares | "Boys vs girls average rank" / "Men vs women average rank" for large rosters | Many `query_player_detail` or `compare_players` calls; may hit round limits. Response `meta.coverage` flags when stats were fetched for fewer than 60% of roster players |
| Inactive players | "How did former member Alex do?" | Active roster only |
| Sparse trends | "Who improved most this month?" | Trend tool needs games in both windows |
| Regional with thin geo | "Who leads in California?" when few venues have state filled | Rankings omit venues without city/state; check `coverage_thin` |
| Ambiguous names | "How is Lucas doing?" with two Lucases | Ambiguity error or wrong match |
| "Most" without metric | "Who is the best in dominos?" | Model must choose rank_score vs wins vs placement |
| Exact counts across many players | "Rank everyone by 2nd-place finishes" | 20-row cap |
| Three or more players together | "Stats when Amelia, Hudson, and Lucas play together" | Head-to-head is two-player only; `compare_players` is career stats, not shared-table only |

### Not supported

| Category | Example questions | Gap |
| -------- | ----------------- | --- |
| Streaks | "Longest win streak?" | Not computed in any Ask tool |
| Rank movement after one game | "Who did Amelia pass when she won last Tuesday?" | Matchup page only |
| Cross game type summary | "Who is best across all our games?" | No multi-type aggregate tool |
| Predictions | "Who will win next month?" | Prompt forbids; no predictive data |
| Arbitrary geo regions | "Who leads on the west side of LA?" | No polygon / bbox tool yet |

---

## Planned expansion

Remaining high-value gaps and proposed tools. Ordered roughly by effort and impact.

| Priority | Tool or change | Unlocks |
| -------- | -------------- | ------- |
| Next | `query_streaks` | Win/loss/podium streaks |
| Next | `query_multi_game_type` | Cross-game-type player summary |
| Later | Inactive player support | Alumni questions |

Example questions and tools are listed in the Ask **Examples** UI (`/insights/ask/examples/`).

Optional HTTP endpoints (for matchup picker UI or marketing embeds, not required for Ask):

| Endpoint | Purpose |
| -------- | ------- |
| `GET /api/groups/{id}/head-to-head/` | Ad-hoc comparison page (`TODO.md`) |
| `GET /api/groups/{id}/hall-of-fame/` | JSON grid for embeds |

---

## Open questions

1. **UI period vs tool period:** Is `all_time: true` enough, or should Ask ignore UI filters server-side when the question says "all time"?
2. **Debug visibility:** `insights_debug_allowed` is open to all users. Keep for demos or restrict to staff?
3. **Head-to-head scope:** Same game type only (current behavior). Ever cross game type?
4. **Inactive players:** Include in roster for Ask name resolution?
5. **Tool round limit:** Raised to 5 rounds (`ASK_MAX_TOOL_ROUNDS`). Enough for typical compare flows; watch debug if complex chains still fail.
6. **Landing demo:** Which questions should be guaranteed supported for portfolio?

---

## Validation checklist (debug mode)

1. POST `/insights/ask/query/` with `include_debug: true` and `refresh: true`.
2. Inspect `debug.tool_rounds`: tool names, arguments, raw JSON results.
3. Confirm period args match the question (`all_time`, `year`, `month`).
4. For placement questions, confirm `placement` is 0-indexed and `game_size` if relevant.
5. Compare tool output to leaderboard/Hall of Fame pages for the same group and filters.

---

## Key source files

| Area | Path |
| ---- | ---- |
| Tool schemas | `leaderlodge/insights/tools/schemas.py` |
| Executor | `leaderlodge/insights/tools/executor.py` |
| Head-to-head | `leaderlodge/insights/tools/head_to_head.py` |
| Hall of Fame | `leaderlodge/insights/tools/hall_of_fame.py` |
| Loss leaders | `leaderlodge/insights/tools/loss_leaders.py` |
| Compare players | `leaderlodge/insights/tools/compare.py` |
| Multi-year rank history | `leaderlodge/insights/tools/rank_history.py` |
| Location resolution | `leaderlodge/insights/tools/locations.py` |
| Placements | `leaderlodge/insights/tools/placements.py` |
| Trends / month leaders | `leaderlodge/insights/tools/trends.py` |
| Standings / player detail | `leaderlodge/insights/tools/standings.py` |
| Rate display / outcome strings | `leaderlodge/insights/tools/rate_display.py` |
| Player resolution | `leaderlodge/insights/tools/players.py` |
| Ask orchestration | `leaderlodge/insights/service.py` |
| System prompt | `leaderlodge/insights/prompts.py` (`ASK_SYSTEM_PROMPT`, `PROMPT_VERSION`) |
| HTTP | `leaderlodge/insights/views.py` (`ask_query`) |
| Ranking source | `leaderlodge/leaderboards/service.py` |
| Tests | `tests/test_insights_tools.py`, `tests/test_insights_ask.py`, `tests/test_insights_ask_integration.py` |
