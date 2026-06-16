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

| player | game_type_code | wins | games_played | rank |
|--------|----------------|------|--------------|------|
| David  | dominos        | 5    | 8            | 1    |
| David  | backgammon     | 2    | 4            | 2    |

`PlayerRanking` fields: `player`, `game_type_code`, `game_type_name`,
`games_played`, `wins`, `win_pct`, `rank`.

### Ranking service

All ranking logic lives in `leaderlodge/leaderboards/service.py` as plain
functions (no strategy classes or inheritance):

- `get_player_rankings(group, game_type_code=None, min_games=1)` -- main entry
- `get_player_stats(group, player)` -- per-game-type stats for a single player

Phase 1 ranks by wins (desc), then games played (desc), within each game type.
The module will be extended in place as weighted ranking is added in Phase 2.

## Score storage

Normalized relational model:

- `Game` -- metadata (group, game type, date, player count)
- `GameParticipantResult` -- one row per player per game (score, result)

## Models

Models are defined but migrations require explicit approval before running
`makemigrations` or `migrate`.
