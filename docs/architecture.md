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
`games_played`, `wins`, `losses`, `win_points`, `win_pct`, `loss_pct`,
`rank_score`, `rank`.

### Ranking service

All ranking logic lives in `leaderlodge/leaderboards/service.py` and
`leaderlodge/leaderboards/ranking.py` as plain functions (no strategy classes):

- `get_player_rankings(group, game_type_code=None, min_games=1)` -- main entry
- `get_group_roster_standings(group, game_type_code, sort, ascending)` -- group detail
- `get_player_stats(group, player)` -- per-game-type stats for a single player

Phase 1 ranks by field-weighted win score within each game type. Each win
contributes `player_count × (double_weight / half_weight)`; ties contribute
half that amount. Rank score is win points divided by weighted games played.

Players must meet `MIN_GAMES_FOR_LEADERBOARD` to appear on the leaderboard page.
The group detail roster shows all players; unqualified players have no rank.

## Score storage

Normalized relational model:

- `Game` -- metadata (group, game type, date, player count)
- `GameParticipantResult` -- one row per player per game (score, result)

## Models

Models are defined but migrations require explicit approval before running
`makemigrations` or `migrate`.
