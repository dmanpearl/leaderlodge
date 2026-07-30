# Rank scoring

> **Companion:** [architecture.md](./architecture.md) (app layout and service entry points)

LeaderLodge ranks players **per group** and **per game type**. Every number on the
leaderboard is derived from recorded game results. This document walks through
each step in order, using the same variable names as the code in
`leaderlodge/leaderboards/ranking.py` and `leaderlodge/leaderboards/service.py`.

Rank assignment is **higher is better**: a larger `rank_score` means a better
standing. Rank 1 is the best.

---

## Scope

- Standings are computed separately for each `(group, game_type_code)` pair.
- A player who plays dominos and mahjongg has two independent rank scores.
- **All-time** leaderboards apply Bayesian experience adjustment (see Step 8).
- **Period** leaderboards (year, month, date range) show raw averages only;
  experience weighting is disabled for those windows.

---

## Step 1: Per-game inputs

Each `GameParticipantResult` row supplies:

| Symbol | Meaning |
|--------|---------|
| `player_count` | Number of **sides** in the game (`Game.player_count`), not head count. A 2-team dominos game with four people has `player_count = 2`. |
| `placement` | 0-indexed finish position (0 = 1st). Tied scores share the lower place. |
| `score` | Recorded score for that side. |
| `result` | Win, loss, tie, or played (no explicit loss). |
| `double_weight` | 2 when the game counts as a double (Dominos winner scored 60+), else 1. |
| `half_weight` | 2 when the game counts as a half (Progressive Rummy), else 1. |
| `low_wins` | Game-type flag. When true (Progressive Rummy), lower raw scores are better. |

Game weight (used in several steps):

```
weight = double_weight / half_weight
```

Examples: a normal game has `weight = 1`. A double dominos game has
`weight = 2`. A half Progressive Rummy game has `weight = 0.5`.

---

## Step 2: Score magnitude (one result)

`score_magnitude` converts the raw score into a single non-negative number where
**larger is always better**, regardless of game type.

**High-wins games** (dominos, mahjongg, pickleball, etc.):

```
score_magnitude = score
```

**Low-wins games** (Progressive Rummy), winner (`placement = 0`):

```
score_magnitude = max(500 - score, 0)
```

The constant `500` is `LOW_WINS_REFERENCE_SCORE` in code.

**Low-wins games**, non-winners:

```
field_max = max(all scores in that game)
score_magnitude = max(field_max - score, 0)
```

A close second earns more magnitude than a distant second.

---

## Step 3: Side finish points (one result)

`side_finish_points` is the rank credit the **side** earned in one game (before
team expansion).

First, placement ratio (how far above last place):

```
slots_above_last = player_count - 1
placement_distance = max(player_count - placement - 1, 0)
placement_ratio = placement_distance / slots_above_last
```

Last place always has `placement_distance = 0`, so `side_finish_points = 0`.

Then:

```
side_finish_points = placement_ratio × player_count × weight × score_magnitude
```

The exponent on `placement_ratio` is `FINISH_POINTS_EXPONENT` (currently `1`).

**Ties** multiply the result by `0.5` (`TIE_WIN_POINTS_FACTOR`).

**Examples** (no tie, `weight = 1`, high-wins, winner score 30):

| Field | `player_count` | `placement` | `placement_ratio` | `score_magnitude` | `side_finish_points` |
|-------|----------------|-------------|-------------------|-------------------|----------------------|
| 2-side win | 2 | 0 | 1.0 | 30 | 1.0 × 2 × 1 × 30 = **60** |
| 5-player win | 5 | 0 | 1.0 | 30 | 1.0 × 5 × 1 × 30 = **150** |
| 5-player 2nd | 5 | 1 | 0.75 | 25 | 0.75 × 5 × 1 × 25 = **93.75** |
| 2-side loss | 2 | 1 | 0.0 | 10 | **0** |

---

## Step 4: Bayesian factor (experience)

Default prior strength:

```
k = LEADERBOARD_BAYESIAN_K   (default 20)
```

For a given weighted games count `g`:

```
bayesian_factor(g) = g / (g + k)
```

When `g = 0`, `bayesian_factor = 0`.

Examples with `k = 20`:

| `g` | `bayesian_factor(g)` |
|-----|----------------------|
| 1 | 1/21 ≈ 0.048 |
| 10 | 10/30 ≈ 0.333 |
| 20 | 20/40 = 0.5 |
| 100 | 100/120 ≈ 0.833 |

This replaced an older **vesting** formula (roughly `raw × (games/threshold)²`).
The **"New" badge** on the all-time leaderboard is UI-only (`games_played < 10`);
it does not change any numbers.

---

## Step 5: Crediting finish points to leaderboard rows

Each side credits one or more leaderboard rows. Wins and `games_played` always
use full weight (`+1` win, `+weight` games) regardless of finish-point
weighting below.

### Solo side

The solo player receives:

```
solo_finish_points += side_finish_points
```

### Team side

The team entity receives full side credit:

```
team_entity_solo_finish_points += side_finish_points
```

Each **member** receives experience-weighted credit (all-time only):

```
member_team_finish_points += side_finish_points × bayesian_factor(member_games_played)
```

`member_games_played` is that member's total weighted games in scope (solo plus
team), computed before this step.

Period-filtered leaderboards skip the multiplier (full `side_finish_points`).

### Totals per row

Each leaderboard row tracks:

```
finish_points_solo   = sum of solo-sourced credits
finish_points_team   = sum of team-sourced credits (individuals only)
finish_points_total  = finish_points_solo + finish_points_team
```

Team entities store their full side credit in `finish_points_solo` only
(`finish_points_team = 0`).

---

## Step 6: Games played and display stats (one player)

Summed across all credited results:

```
games_played = sum(weight from each credited result)
```

Wins, losses, and win/loss percentages use the same weights. They are display
stats and do not change sort order.

---

## Step 7: Raw rank score (one player)

```
raw_rank_score = finish_points_total / games_played
```

When `games_played = 0`, `raw_rank_score = 0`.

---

## Step 8: Rank score (one player, displayed)

**Period-filtered leaderboard:**

```
rank_score = raw_rank_score
```

**All-time leaderboard, team entity row:**

```
collective_games = average(member_games_played for each team member)
rank_score = raw_rank_score × bayesian_factor(collective_games)
```

**All-time leaderboard, individual person:**

Bayesian applies to solo-sourced points only. Team-sourced points were already
scaled at credit time (Step 5).

```
solo_raw   = finish_points_solo / games_played
team_raw   = finish_points_team / games_played
rank_score = solo_raw × bayesian_factor(games_played) + team_raw
```

When `games_played = 0`, `rank_score = 0`.

---

## Step 9: Rank order (sorting)

Players are sorted by `rank_score` descending. Ties break in order:

1. Higher `games_played`
2. Higher `finish_points_total`
3. Display name (case-insensitive, A to Z)

Rank numbers (1, 2, 3, ...) are assigned after sorting.

---

## Worked example: solo dominos win

Alice beats Bob in a 2-player dominos game. Alice scores 30, Bob scores 10.
`player_count = 2`, `weight = 1`, high-wins.

**Alice (winner):**

```
side_finish_points = 1.0 × 2 × 1 × 30 = 60
finish_points_solo = 60
finish_points_team = 0
finish_points_total = 60
games_played = 1
raw_rank_score = 60 / 1 = 60
rank_score = (60/1) × bayesian_factor(1) + 0 = 60 × (1/21) ≈ 2.86
```

**Bob (loser):**

```
side_finish_points = 0
rank_score = 0
```

---

## Worked example: team win (veteran + rookie)

Nancy has 20 prior solo dominos games. Zach has none. Nancy+Zach win one team
game (side score 30 vs 10). `player_count = 2`, `weight = 1`, so
`side_finish_points = 60`.

After the team game:

| Row | `games_played` | `finish_points_solo` | `finish_points_team` | `finish_points_total` |
|-----|----------------|----------------------|----------------------|-----------------------|
| `"Nancy+Zach"` (team) | 1 | 60 | 0 | 60 |
| Nancy (individual) | 21 | ~1200 (prior solo) | 60 × 21/41 ≈ 30.7 | ~1230.7 |
| Zach (individual) | 1 | 0 | 60 × 1/21 ≈ 2.9 | ≈ 2.9 |

**Zach (rookie) rank score:**

```
solo_raw = 0
team_raw = 2.9 / 1 = 2.9
rank_score = 0 + 2.9 = 2.9
```

**Nancy (veteran) rank score** (simplified; prior solo total ≈ 1200):

```
solo_raw ≈ 1200 / 21 ≈ 57.1
team_raw ≈ 30.7 / 21 ≈ 1.5
rank_score ≈ 57.1 × (21/41) + 1.5 ≈ 30.7
```

Zach no longer inherits Nancy's full 60-point side credit on the individual
leaderboard. The team row `"Nancy+Zach"` still carries the full 60.

---

## Other notes

### Double and half games

`weight` flows into `side_finish_points`, `games_played`, and wins/losses. A
double game doubles those contributions. A half game halves them. There is no
separate rank multiplier for half games yet.

### Win points

`win_points = player_count × weight` on wins (half weight on ties) is tracked
for display and insights but **not** used in `rank_score` or sort order.

### People vs team leaderboards

The people leaderboard shows individuals only. The team leaderboard shows team
entities. Both use the formulas above.

### Code reference

| Step | Module | Functions |
|------|--------|-----------|
| Magnitude and side points | `leaderlodge/leaderboards/ranking.py` | `compute_score_magnitude`, `compute_finish_points` |
| Experience weight and rank score | `leaderlodge/leaderboards/ranking.py` | `team_member_finish_credit`, `compute_display_rank_score`, `compute_bayesian_factor` |
| Aggregation | `leaderlodge/leaderboards/service.py` | `_finish_points_by_player`, `_standings_for_game_type` |
| Team expansion | `leaderlodge/groups/teams.py` | `leaderboard_credit_players`, `effective_games_played_for_player` |
