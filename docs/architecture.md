# LeaderLodge Architecture (Phase 1)

## App layout

| App | Responsibility |
|-----|----------------|
| `leaderlodge.core` | Dashboard, home |
| `leaderlodge.accounts` | Login / logout |
| `leaderlodge.groups` | Groups, memberships, group players |
| `leaderlodge.games` | Game records, registry, per-game validation |
| `leaderlodge.leaderboards` | Ranking display; logic in `service.py` |

Game subpackages (`dominos/`, `backgammon/`, etc.) contain validation rules only.

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
`rank_score`, `rank`.

### Ranking service

All ranking logic lives in `leaderlodge/leaderboards/service.py` and
`leaderlodge/leaderboards/ranking.py` as plain functions (no strategy classes):

- `get_player_rankings(group, game_type_code=None)` -- main entry
- `get_player_rank_detail(group, player, game_type_code)` -- rank breakdown for one player
- `get_group_roster_standings(group, game_type_code, sort, ascending)` -- group detail
- `get_player_stats(group, player)` -- per-game-type stats for a single player

Phase 2 ranks by field-weighted finish points within each game type. For each
game result, normalized placement distance is raised to the power 1.5, then
multiplied by player count and game weight (double/half). Last place earns 0.
Tied scores use lower-place tie ranking (ties share the worst placement in
their score group). Ties multiply finish credit by 0.5. Raw rank score is
total finish points divided by weighted games played.

High-wins game types (dominos, backgammon, mahjongg): unvested scores are
multiplied by vesting progress (lower displayed score until fully vested at
`LEADERBOARD_VESTING_COUNT` games). Higher displayed score is better.

Progressive Rummy (low-wins): unvested scores use vesting progress squared
(`raw x vesting^2`) so one-game peaks are damped without inverting the scale.
Higher displayed score is better (same sort order as other game types). Half
games still count at 0.5x in games/wins totals only; no extra rank multiplier yet.

All players with at least one recorded game appear on the leaderboard.
The group detail roster shows every active player; unranked rows have no games.

## Score storage

Normalized relational model:

- `Game` -- metadata (group, game type, date, player count)
- `GameParticipantResult` -- one row per player per game (score, result)

## Models

Models are defined but migrations require explicit approval before running
`makemigrations` or `migrate`.
