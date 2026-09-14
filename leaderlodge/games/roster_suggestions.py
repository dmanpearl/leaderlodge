"""Smart side suggestions for Record Game based on recent play history."""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.utils import timezone

from leaderlodge.games.models import Game
from leaderlodge.games.registry import GAME_TYPES, GameTypeDefinition
from leaderlodge.games.reuse_players import (
    REUSE_PLAYERS_MAX_SCAN,
    _lineup_key,
    participant_rows_from_game,
)
from leaderlodge.groups.models import Group
from leaderlodge.groups.teams import team_member_players

MAX_SUGGESTIONS = 8
MAX_LINEUP_SUGGESTIONS = 6
SCAN_GAMES = 20
MIN_RECENT_PLAYERS = 4


@dataclass
class _PlayerActivity:
    player_id: int
    label: str
    last_date: date | None = None
    play_count: int = 0
    solo_count: int = 0
    team_count: int = 0

    @property
    def recency_rank(self) -> int:
        if self.last_date is None:
            return 9999
        return (timezone.localdate() - self.last_date).days


@dataclass
class _PairActivity:
    member_ids: frozenset[int]
    labels: tuple[str, ...]
    last_date: date | None = None
    play_count: int = 0

    @property
    def label(self) -> str:
        return "+".join(sorted(self.labels, key=str.lower))

    @property
    def recency_rank(self) -> int:
        if self.last_date is None:
            return 9999
        return (timezone.localdate() - self.last_date).days


@dataclass
class _HistoryScan:
    players: dict[int, _PlayerActivity] = field(default_factory=dict)
    pairs: dict[frozenset[int], _PairActivity] = field(default_factory=dict)
    solo_sides: int = 0
    team_sides: int = 0
    dates_seen: set[date] = field(default_factory=set)


def _member_ids_for_result(result) -> frozenset[int]:
    player = result.player
    if player.is_team:
        return frozenset(member.pk for member in team_member_players(player))
    return frozenset([player.pk])


def _member_labels_for_result(result, labels: dict[int, str]) -> tuple[str, ...]:
    member_ids = _member_ids_for_result(result)
    return tuple(
        labels.get(member_id, f"Player {member_id}") for member_id in member_ids
    )


def _scan_recent_history(group: Group, game_type_code: str) -> _HistoryScan:
    from leaderlodge.groups.names import apply_label_overrides

    scan = _HistoryScan()
    games = (
        Game.objects.filter(group_id=group.pk, game_type_code=game_type_code)
        .order_by("-played_on", "-created_at", "-pk")
        .prefetch_related(
            "participant_results__player",
            "participant_results__player__linked_user",
            "participant_results__player__team_members__member__linked_user",
        )[:SCAN_GAMES]
    )

    label_players = []
    for game in games:
        for result in game.participant_results.all():
            label_players.append(result.player)
            if result.player.is_team:
                label_players.extend(team_member_players(result.player))
    apply_label_overrides(label_players)
    labels = {player.pk: player.display_label for player in label_players}

    for game in games:
        scan.dates_seen.add(game.played_on)
        for result in game.participant_results.all():
            player = result.player
            if not player.is_active:
                continue
            member_ids = _member_ids_for_result(result)
            if not member_ids:
                continue
            member_labels = _member_labels_for_result(result, labels)
            is_team_side = len(member_ids) > 1
            if is_team_side:
                scan.team_sides += 1
                pair = scan.pairs.setdefault(
                    member_ids,
                    _PairActivity(member_ids=member_ids, labels=member_labels),
                )
                pair.play_count += 1
                if pair.last_date is None or game.played_on > pair.last_date:
                    pair.last_date = game.played_on
            else:
                scan.solo_sides += 1

            for member_id in member_ids:
                activity = scan.players.setdefault(
                    member_id,
                    _PlayerActivity(
                        player_id=member_id,
                        label=labels.get(member_id, f"Player {member_id}"),
                    ),
                )
                activity.play_count += 1
                if activity.last_date is None or game.played_on > activity.last_date:
                    activity.last_date = game.played_on
                if is_team_side:
                    activity.team_count += 1
                else:
                    activity.solo_count += 1

    return scan


def _player_payload(activity: _PlayerActivity) -> dict:
    return {
        "player_id": activity.player_id,
        "guest_name": "",
        "label": activity.label,
    }


def _pair_blocked(member_ids: frozenset[int], exclude: set[int]) -> bool:
    return bool(member_ids & exclude)


def _solo_score(activity: _PlayerActivity, *, solo_weight: float) -> float:
    today = timezone.localdate()
    score = float(activity.play_count) * 5.0
    if activity.last_date == today:
        score += 80.0
    elif activity.last_date and activity.last_date >= today - timedelta(days=1):
        score += 40.0
    score += max(0.0, 30.0 - float(activity.recency_rank) * 3.0)
    score *= solo_weight
    return score


def _pair_score(pair: _PairActivity, *, team_weight: float) -> float:
    today = timezone.localdate()
    score = float(pair.play_count) * 10.0
    if pair.last_date == today:
        score += 100.0
    elif pair.last_date and pair.last_date >= today - timedelta(days=1):
        score += 50.0
    score += max(0.0, 30.0 - float(pair.recency_rank) * 3.0)
    score *= team_weight
    return score


def _predicted_pairs(
    scan: _HistoryScan,
    *,
    exclude: set[int],
    team_weight: float,
) -> list[tuple[float, _PairActivity]]:
    today = timezone.localdate()
    active_today = [
        activity
        for activity in scan.players.values()
        if activity.last_date == today and activity.player_id not in exclude
    ]
    active_today.sort(
        key=lambda item: (-item.play_count, item.recency_rank, item.label)
    )
    if len(active_today) < 2:
        return []

    observed_today_pairs = {
        member_ids for member_ids, pair in scan.pairs.items() if pair.last_date == today
    }
    predicted: list[tuple[float, _PairActivity]] = []
    limit = min(len(active_today), 6)
    for index, left in enumerate(active_today[:limit]):
        for right in active_today[index + 1 : limit]:
            member_ids = frozenset([left.player_id, right.player_id])
            if len(member_ids) != 2:
                continue
            if member_ids in scan.pairs or member_ids in observed_today_pairs:
                continue
            if _pair_blocked(member_ids, exclude):
                continue
            labels = (left.label, right.label)
            pair = _PairActivity(member_ids=member_ids, labels=labels, last_date=today)
            score = 25.0 + float(left.play_count + right.play_count) * team_weight
            predicted.append((score, pair))
    predicted.sort(key=lambda item: (-item[0], item[1].label.lower()))
    return predicted


def _matches_query(payload: dict, query: str) -> bool:
    cleaned = query.strip()
    if not cleaned:
        return True
    from leaderlodge.groups.fuzzy import score_fuzzy_match

    if score_fuzzy_match(cleaned, payload["label"]) >= 0:
        return True
    for player in payload.get("players") or []:
        label = player.get("label") or ""
        if score_fuzzy_match(cleaned, label) >= 0:
            return True
    return False


def suggest_side_entries(
    group: Group,
    game_type_code: str,
    *,
    exclude_player_ids: set[int] | None = None,
    query: str = "",
    teammate_mode: bool = False,
    limit: int = MAX_SUGGESTIONS,
) -> list[dict]:
    """Ranked solo and team sides to add next on Record Game."""
    if game_type_code not in GAME_TYPES or limit <= 0:
        return []

    exclude = set(exclude_player_ids or ())
    scan = _scan_recent_history(group, game_type_code)
    if not scan.players:
        return []

    total_sides = scan.solo_sides + scan.team_sides
    team_ratio = scan.team_sides / total_sides if total_sides else 0.0
    if team_ratio >= 0.65:
        team_weight, solo_weight = 1.35, 0.55
    elif team_ratio <= 0.35:
        team_weight, solo_weight = 0.55, 1.35
    else:
        team_weight, solo_weight = 1.0, 1.0

    candidates: list[tuple[float, str, dict]] = []

    for pair in scan.pairs.values():
        if len(pair.member_ids) != 2 or _pair_blocked(pair.member_ids, exclude):
            continue
        score = _pair_score(pair, team_weight=team_weight)
        players = [
            _player_payload(scan.players[member_id])
            for member_id in sorted(
                pair.member_ids, key=lambda pk: scan.players[pk].label.lower()
            )
            if member_id in scan.players
        ]
        if len(players) != 2:
            continue
        candidates.append(
            (
                score,
                pair.label.lower(),
                {
                    "kind": "team",
                    "label": pair.label,
                    "players": players,
                },
            )
        )

    for score, pair in _predicted_pairs(scan, exclude=exclude, team_weight=team_weight):
        players = [
            _player_payload(scan.players[member_id])
            for member_id in sorted(
                pair.member_ids, key=lambda pk: scan.players[pk].label.lower()
            )
            if member_id in scan.players
        ]
        if len(players) != 2:
            continue
        candidates.append(
            (
                score,
                pair.label.lower(),
                {
                    "kind": "team",
                    "label": pair.label,
                    "players": players,
                },
            )
        )

    for activity in scan.players.values():
        if activity.player_id in exclude:
            continue
        score = _solo_score(activity, solo_weight=solo_weight)
        candidates.append(
            (
                score,
                activity.label.lower(),
                {
                    "kind": "solo",
                    "label": activity.label,
                    "players": [_player_payload(activity)],
                },
            )
        )

    if teammate_mode:
        candidates = [item for item in candidates if item[2]["kind"] == "solo"]

    candidates.sort(key=lambda item: (-item[0], item[1]))

    suggestions: list[dict] = []
    seen_labels: set[str] = set()
    seen_member_sets: set[frozenset[int]] = set()
    for _score, _sort_label, payload in candidates:
        if not _matches_query(payload, query):
            continue
        label_key = payload["label"].lower()
        member_ids = frozenset(
            player["player_id"]
            for player in payload["players"]
            if player.get("player_id")
        )
        if label_key in seen_labels:
            continue
        if len(member_ids) > 1 and member_ids in seen_member_sets:
            continue
        seen_labels.add(label_key)
        if member_ids:
            seen_member_sets.add(member_ids)
        suggestions.append(payload)
        if len(suggestions) >= limit:
            break

    if (
        len({activity.player_id for activity in scan.players.values()})
        < MIN_RECENT_PLAYERS
    ):
        return suggestions

    return suggestions


def _side_payload_from_row(row: dict) -> dict | None:
    players = []
    player_id = row.get("player_id")
    guest_name = (row.get("guest_name") or "").strip()
    if player_id:
        players.append(
            {
                "player_id": int(player_id),
                "guest_name": "",
                "label": row.get("display_label") or "",
            }
        )
    elif guest_name:
        players.append(
            {
                "player_id": None,
                "guest_name": guest_name,
                "label": row.get("display_label") or guest_name,
            }
        )
    else:
        return None

    teammate_id = row.get("teammate_player_id")
    if teammate_id:
        players.append(
            {
                "player_id": int(teammate_id),
                "guest_name": "",
                "label": row.get("teammate_display_label") or "",
            }
        )

    kind = "team" if len(players) > 1 else "solo"
    label = row.get("display_label") or players[0]["label"]
    return {"kind": kind, "label": label, "players": players}


def _lineup_option_from_rows(
    rows: list[dict],
    *,
    source: str,
    game_id: int | None = None,
) -> dict | None:
    sides = []
    for row in rows:
        side = _side_payload_from_row(row)
        if side:
            sides.append(side)
    if len(sides) < 2:
        return None
    labels = [side["label"] for side in sides]
    option = {
        "summary": ", ".join(labels),
        "labels": labels,
        "sides": sides,
        "source": source,
        "lineup_key": _lineup_key(rows),
    }
    if game_id is not None:
        option["game_id"] = game_id
    return option


def _lineup_key_from_side_payloads(sides: list[dict]) -> frozenset:
    member_sets: list[frozenset[int]] = []
    for side in sides:
        member_ids = {
            int(player["player_id"])
            for player in side.get("players") or []
            if player.get("player_id")
        }
        if member_ids:
            member_sets.append(frozenset(member_ids))
    return frozenset(member_sets)


def _side_payload_from_pair(pair: _PairActivity, scan: _HistoryScan) -> dict:
    players = []
    for member_id in sorted(pair.member_ids):
        activity = scan.players.get(member_id)
        if activity is None:
            continue
        players.append(_player_payload(activity))
    return {"kind": "team", "label": pair.label, "players": players}


def _typical_side_count(games: list[Game], game_type: GameTypeDefinition) -> int:
    counts: list[int] = []
    for game in games:
        count = len(game.participant_results.all())
        if count >= game_type.min_players:
            counts.append(count)
    if not counts:
        return game_type.min_players
    return max(game_type.min_players, min(max(counts), game_type.max_players))


def _predicted_team_lineups(
    scan: _HistoryScan,
    *,
    side_count: int,
    team_weight: float,
    seen_keys: set[frozenset],
    limit: int,
) -> list[dict]:
    if side_count != 2 or limit <= 0:
        return []

    pair_candidates: list[tuple[float, _PairActivity]] = []
    for pair in scan.pairs.values():
        pair_candidates.append((_pair_score(pair, team_weight=team_weight), pair))
    pair_candidates.extend(
        _predicted_pairs(scan, exclude=set(), team_weight=team_weight)
    )
    pair_candidates.sort(key=lambda item: (-item[0], item[1].label.lower()))

    lineups: list[tuple[float, dict]] = []
    for left_index, (left_score, left_pair) in enumerate(pair_candidates):
        for right_score, right_pair in pair_candidates[left_index + 1 :]:
            if left_pair.member_ids & right_pair.member_ids:
                continue
            sides = [
                _side_payload_from_pair(left_pair, scan),
                _side_payload_from_pair(right_pair, scan),
            ]
            if any(len(side["players"]) < 2 for side in sides):
                continue
            lineup_key = _lineup_key_from_side_payloads(sides)
            if not lineup_key or lineup_key in seen_keys:
                continue
            labels = [side["label"] for side in sides]
            lineups.append(
                (
                    left_score + right_score,
                    {
                        "summary": ", ".join(labels),
                        "labels": labels,
                        "sides": sides,
                        "source": "predicted",
                        "lineup_key": lineup_key,
                    },
                )
            )

    lineups.sort(key=lambda item: (-item[0], item[1]["summary"].lower()))
    return [item[1] for item in lineups[:limit]]


def _predicted_solo_lineups(
    scan: _HistoryScan,
    *,
    side_count: int,
    solo_weight: float,
    seen_keys: set[frozenset],
    limit: int,
) -> list[dict]:
    if limit <= 0:
        return []

    ranked = sorted(
        scan.players.values(),
        key=lambda activity: (
            -_solo_score(activity, solo_weight=solo_weight),
            activity.label.lower(),
        ),
    )
    lineups: list[tuple[float, dict]] = []
    combo_limit = min(len(ranked), side_count + 4)
    for combo in itertools.combinations(ranked[:combo_limit], side_count):
        sides = [
            {
                "kind": "solo",
                "label": activity.label,
                "players": [_player_payload(activity)],
            }
            for activity in combo
        ]
        lineup_key = _lineup_key_from_side_payloads(sides)
        if not lineup_key or lineup_key in seen_keys:
            continue
        score = sum(
            _solo_score(activity, solo_weight=solo_weight) for activity in combo
        )
        labels = [side["label"] for side in sides]
        lineups.append(
            (
                score,
                {
                    "summary": ", ".join(labels),
                    "labels": labels,
                    "sides": sides,
                    "source": "predicted",
                    "lineup_key": lineup_key,
                },
            )
        )

    lineups.sort(key=lambda item: (-item[0], item[1]["summary"].lower()))
    return [item[1] for item in lineups[:limit]]


def suggest_lineup_entries(
    group: Group,
    game_type_code: str,
    *,
    limit: int = MAX_LINEUP_SUGGESTIONS,
) -> list[dict]:
    """Full-game lineup suggestions: replay recent matchups plus predicted combos."""
    if game_type_code not in GAME_TYPES or limit <= 0:
        return []

    game_type = GAME_TYPES[game_type_code]
    games = list(
        Game.objects.filter(group_id=group.pk, game_type_code=game_type_code)
        .order_by("-played_on", "-created_at", "-pk")
        .prefetch_related(
            "participant_results__player__linked_user",
            "participant_results__player__team_members__member__linked_user",
        )[:REUSE_PLAYERS_MAX_SCAN]
    )

    options: list[dict] = []
    seen_keys: set[frozenset] = set()
    for game in games:
        if len(options) >= limit:
            break
        rows = participant_rows_from_game(game)
        option = _lineup_option_from_rows(rows, source="replay", game_id=game.pk)
        if option is None:
            continue
        lineup_key = option.pop("lineup_key")
        if lineup_key in seen_keys:
            continue
        seen_keys.add(lineup_key)
        options.append(option)

    if len(options) < limit and games:
        scan = _scan_recent_history(group, game_type_code)
        if scan.players:
            side_count = _typical_side_count(games, game_type)
            total_sides = scan.solo_sides + scan.team_sides
            team_ratio = scan.team_sides / total_sides if total_sides else 0.0
            if team_ratio >= 0.65:
                team_weight, solo_weight = 1.35, 0.55
            elif team_ratio <= 0.35:
                team_weight, solo_weight = 0.55, 1.35
            else:
                team_weight, solo_weight = 1.0, 1.0

            if team_ratio >= 0.5 and side_count == 2:
                predicted = _predicted_team_lineups(
                    scan,
                    side_count=side_count,
                    team_weight=team_weight,
                    seen_keys=seen_keys,
                    limit=limit - len(options),
                )
            else:
                predicted = _predicted_solo_lineups(
                    scan,
                    side_count=side_count,
                    solo_weight=solo_weight,
                    seen_keys=seen_keys,
                    limit=limit - len(options),
                )
            for option in predicted:
                lineup_key = option.pop("lineup_key")
                seen_keys.add(lineup_key)
                options.append(option)

    return options
