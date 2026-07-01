# Ask the Lodge: capability audit and expansion plan

> **Companion:** [ai-insights.md](./ai-insights.md) (shipped surfaces, API contract, UX, env, testing). This document tracks what Ask can answer, tool limits, and planned expansion.

**Last reviewed:** 2026-06-30

---

## How Ask works (constraints that affect every answer)

| Constraint | Value | Effect |
| ---------- | ----- | ------ |
| Tool rounds | Up to 3 | Complex questions that need many sequential lookups may fail with "exceeded the tool call limit" |
| Row limit | 1 to 20 per tool (`ToolExecutor.MAX_LIMIT`) | "Everyone in the group" questions truncate |
| Rankings | Python ORM only | The model never computes `rank_score`, placement counts, or trends |
| Scope | One group per request | No cross-group comparisons |
| Default period | Ask page filters (`year` / `month` on `POST /insights/ask/query/`) | When a tool omits `year` and `month`, the UI-selected period applies |
| All-time override | `all_time: true` on period-aware tools | Ignores the Ask page default period |
| Player roster | Active players only, embedded in the user message | Inactive or historical players may not resolve |
| Placement index | 0 = 1st, 1 = 2nd, 2 = 3rd in tool args | The model must translate "2nd place" to `placement=1` |
| Score direction | `score_direction` on game-type tool results (`low_wins` or `high_wins`) | Progressive Rummy is low-score-wins; do not treat higher raw points as better |
| Debug | `include_debug: true` on any insight POST | Returns `tool_rounds`, `available_tools`, full LLM message chain |

---

## Ask tool catalog

### `list_game_types`

No parameters. Returns game type codes that have at least one recorded game in the group.

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

Returns ranked rows: `rank`, `rank_score`, `games_played`, `wins`, `win_pct`.

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

Returns rank stats, placement breakdown, `best_score`, `worst_score`, `first_game_date`, `last_game_date`, `date_range_label`, `podium_count`, `podium_pct`, and `tie_count`.

### `query_head_to_head`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `game_type_code` | Yes | |
| `player_a_id` or `player_a_query` | One of | First player |
| `player_b_id` or `player_b_query` | One of | Second player |
| `year`, `month`, `all_time` | No | Period filter on shared games |
| `game_size` | No | Optional player-count filter |

Returns `games_together`, and per-player `games_played`, `wins`, `ties`, `losses` (when the game type supports losses) for games **both players attended** (including games with other players at the table).

### `query_hall_of_fame`

| Parameter | Required | Notes |
| --------- | -------- | ----- |
| `granularity` | No | `year` (default) or `month` |
| `game_type_code` | No | Filter to one game type |
| `limit` | No | Max period rows, default 10, max 20 |

Returns period leaders like the Hall of Fame grid: `period_label`, leader `display_label`, `rank_score` per game type.

---

## Capability matrix

### Supported (reliable when the model picks the right tool and args)

| Category | Example questions | Tool(s) |
| -------- | ----------------- | ------- |
| Current standings | "Who leads dominos all time?" | `query_leaderboard` + `all_time: true` |
| Period standings | "Who was on top in 2025?" / "March 2026 leaderboard" | `query_leaderboard` with `year` / `month` |
| Field-size standings | "Who leads 5-player dominos?" | `query_leaderboard` + `game_size` |
| Placement frequency | "Who finishes 2nd most in dominos?" | `query_placement_leaders`, `placement=1` |
| Placement + period | "Who got 2nd place most in January 2026?" | `query_placement_leaders`, `placement=1`, `month=1`, `year=2026` |
| Placement + month (all years) | "Who gets 2nd most every January?" | `query_placement_leaders`, `placement=1`, `month=1` |
| Monthly leaders | "Who wins most in December?" | `query_month_leaders`, `month=12`, `metric=wins` |
| Monthly rank score | "Best rank score in June 2025" | `query_month_leaders`, `year=2025`, `month=6` |
| Trends | "Who is improving most in the last quarter?" | `query_rank_trends`, `days=90` |
| Player snapshot | "How is Nancy doing in dominos?" | `query_player_detail`, `player_query` |
| Player placement mix | "What place does David finish most often?" | `query_player_detail` (read `placements`) |
| Score highlights | "What was Nancy's best dominos score?" | `query_player_detail` (`best_score`, `worst_score`) |
| Player dates and podiums | "When did Nancy last play?" / "How often does she podium?" | `query_player_detail` |
| Head-to-head | "Who wins more when Nancy and David play together?" | `query_head_to_head` |
| Head-to-head (alt phrasing) | "Nancy vs David: who wins when they share a table?" | `query_head_to_head` |
| Hall of Fame / dynasty | "Who dominated across years?" / "Repeat monthly winners?" | `query_hall_of_fame` |
| Period winners by game | "Who won 2024 in each game?" | `query_hall_of_fame`, `granularity=year` |
| Roster discovery | "Who is in our group?" | `list_group_players` |
| Game types | "What games do we track?" | `list_game_types` |
| Two-player career compare | "How do Nancy and David stack up in dominos?" | Two `query_player_detail` calls, or `query_head_to_head` for shared-table stats |

### Partial or unreliable

| Category | Example questions | Why unreliable |
| -------- | ----------------- | -------------- |
| UI period vs question intent | Ask filter set to "2025" but question says "all time" | Model may omit `all_time: true` despite prompt guidance |
| Placement without field size | "Who finishes last?" in groups that mix 3- and 5-player games | Last placement index depends on `game_size` |
| Multi-tool chains | "Compare dominos and mahjongg leaders, then who improves faster" | May exceed 3 rounds |
| Inactive players | "How did former member Alex do?" | Active roster only |
| Sparse trends | "Who improved most this month?" | Trend tool needs games in both windows |
| Ambiguous names | "How is Pat doing?" with two Pats | Ambiguity error or wrong match |
| "Most" without metric | "Who is the best in dominos?" | Model must choose rank_score vs wins vs placement |
| Last place / loss leaders | "Who loses most?" | No dedicated loss-leader tool yet |
| Exact counts across many players | "Rank everyone by 2nd-place finishes" | 20-row cap |
| Three or more players together | "Stats when Nancy, David, and Pat play together" | Head-to-head is two-player only |

### Not supported

| Category | Example questions | Gap |
| -------- | ----------------- | --- |
| Specific game | "What happened in the game on 3/15/2026?" | No game-level tool |
| Location stats | "Who leads at Joe's house?" | No location filter on Ask tools |
| Custom date range | "Leaders from Spring Break week" | Calendar year/month or fixed-day trend windows only |
| Streaks | "Longest win streak?" | Not computed in any Ask tool |
| Rank movement after one game | "Who did Nancy pass when she won last Tuesday?" | Matchup page only |
| Cross game type summary | "Who is best across all our games?" | No multi-type aggregate tool |
| Predictions | "Who will win next month?" | Prompt forbids; no predictive data |

---

## Planned expansion

Remaining high-value gaps and proposed tools. Ordered roughly by effort and impact.

| Priority | Tool or change | Unlocks |
| -------- | -------------- | ------- |
| Next | `query_loss_leaders` | "Who loses most?" for game types with losses |
| Next | `compare_players` | Side-by-side stats for 2 to 5 players in one tool round |
| Next | `query_date_range_leaderboard` | Custom week or date-range leaders |
| Next | `query_location_leaderboard` | Venue-specific leaders |
| Later | `query_game_detail` | "Tell me about the game on ..." |
| Later | `query_streaks` | Win/loss/podium streaks |
| Later | `query_multi_game_type` | Cross-game-type player summary |
| Later | Inactive player support | Alumni questions |
| Later | Configurable tool round limit | Deep multi-step questions without hitting 3-round cap |

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
5. **Tool round limit:** Stay at 3 or increase as the catalog grows?
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
| Placements | `leaderlodge/insights/tools/placements.py` |
| Trends / month leaders | `leaderlodge/insights/tools/trends.py` |
| Standings / player detail | `leaderlodge/insights/tools/standings.py` |
| Player resolution | `leaderlodge/insights/tools/players.py` |
| Ask orchestration | `leaderlodge/insights/service.py` |
| System prompt | `leaderlodge/insights/prompts.py` (`ASK_SYSTEM_PROMPT`, `PROMPT_VERSION`) |
| HTTP | `leaderlodge/insights/views.py` (`ask_query`) |
| Ranking source | `leaderlodge/leaderboards/service.py` |
| Tests | `tests/test_insights_tools.py`, `tests/test_insights_ask.py`, `tests/test_insights_ask_integration.py` |
