# LeaderLodge Architecture

## App layout

| App | Responsibility |
|-----|----------------|
| `leaderlodge.core` | Dashboard, home |
| `leaderlodge.accounts` | Login / logout |
| `leaderlodge.groups` | Groups, memberships, group players |
| `leaderlodge.games` | Game records, registry, per-game validation. To add a type: [Adding a new game type](./adding-a-game-type.md) |
| `leaderlodge.leaderboards` | Ranking display; logic in `service.py` |
| `leaderlodge.insights` | AI narration over computed stats. See [ai-insights.md](./ai-insights.md). |

Game subpackages (`dominos/`, `backgammon/`, etc.) contain validation rules only.

## AI insights

LeaderLodge computes rankings in Python; the **insights** app calls cloud LLM APIs to explain them. Full design: **[ai-insights.md](./ai-insights.md)**.

Two modes:

1. **Contextual insights** on rank detail, leaderboard, Hall of Fame, matchup, and game detail. Python pre-builds JSON for the open page; the LLM narrates from that snapshot (presets or a short custom question).
2. **Ask the Lodge** at `/insights/ask/`. Free-form questions; the LLM calls validated Python tools that run ORM queries, then narrates the results.

| Surface | Entry |
|---------|-------|
| Player, group, matchup insights | Insights button (`btn-insights`, `bi-stars`) on each page |
| Ask the Lodge | Navbar **Ask**, Account menu **Ask the Lodge** |

**Backend:** `leaderlodge/insights/` (context builders, `POST /insights/player/`, `/group/`, `/matchup/`, `POST /insights/ask/query/`, tools in `insights/tools/`, rate limits in `limits.py` / `rate_limit.py`, disabled by default).

**UI:** `static/css/insights.css`, `templates/includes/btn_insights.html`, offcanvas panels + `insights_panel.js`, Ask page + `ask_lodge.js`.

## Leaderboard design

Rankings are **per game type within a group**. A player who plays multiple game
types receives one `PlayerRanking` row per game type.

Example: David plays dominos and backgammon in Group A:

| player | game_type_code | wins | games_played | rank_score | rank |
|--------|----------------|------|--------------|------------|------|
| David  | dominos        | 5    | 8            | 1.75       | 1    |
| David  | backgammon     | 2    | 4            | 2.00       | 2    |

`PlayerRanking` fields: `player`, `game_type_code`, `game_type_name`,
`games_played`, `wins`, `losses`, `win_points`, `finish_points`, `win_pct`, `loss_pct`,
`rank_score`, `rank`, `longest_streak`, `current_streak`.

### Ranking service

Full step-by-step formulas: **[rank-scoring.md](./rank-scoring.md)**.

All ranking logic lives in `leaderlodge/leaderboards/service.py` and
`leaderlodge/leaderboards/ranking.py` as plain functions (no strategy classes):

- `get_player_rankings(group, game_type_code=None)` -- main entry
- `get_player_rank_detail(group, player, game_type_code)` -- rank breakdown for one player
- `get_group_roster_standings(group, game_type_code, sort, ascending)` -- group detail
- `get_player_stats(group, player)` -- per-game-type stats for a single player

Leaderboards rank by field-weighted finish points within each game type. For each
game result, normalized placement distance is multiplied by player count, game
weight (double/half), and in-game score magnitude. High-wins games use the raw
score; Progressive Rummy winners use a fixed reference minus their score
(performance alone), and other low-wins finishers use field max minus score so a
close second earns more than a far second. Last place earns 0 placement credit.
Tied scores use lower-place tie ranking. Ties multiply finish credit by 0.5. Raw
rank score is total finish points divided by weighted games played.

All game types: raw rank score is multiplied by a Bayesian factor
(`games / (games + k)`). Individuals use `k = LEADERBOARD_BAYESIAN_K` (default
20) against their own total games; Bayesian applies to solo-sourced finish
points only, since team-sourced points are scaled at credit time. Team rows use
a smaller `k = LEADERBOARD_TEAM_BAYESIAN_K` (default 8) against the pairing's
own games, not member career totals or a member average, since a specific pair
accumulates games far more slowly than an individual who rotates partners. See
[rank-scoring.md](./rank-scoring.md).

All players with at least one recorded game appear on the leaderboard.
The group detail roster shows every active player; unranked rows have no games.

## Score storage

Normalized relational model:

- `Game` -- metadata (group, game type, date, player count)
- `GameParticipantResult` -- one row per player per game (score, result)

## Models

Models are defined but migrations require explicit approval before running
`makemigrations` or `migrate`.
