from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import transaction

from leaderlodge.games.models import Game, GameParticipantResult, GameScoreChangeLog
from leaderlodge.games.scoring import assign_results_from_scores, compute_double_weight
from leaderlodge.groups.models import GroupPlayer, Location

_UNCHANGED = object()


@dataclass(frozen=True)
class RecalculateSummary:
    game: Game
    log: GameScoreChangeLog | None
    participants_updated: int
    double_weight_changed: bool
    location_changed: bool = False
    date_changed: bool = False

    @property
    def logs(self) -> list[GameScoreChangeLog]:
        return [self.log] if self.log is not None else []


def user_can_edit_game_scores(user: AbstractBaseUser | None) -> bool:
    """Staff may use management commands and edit any game."""
    if user is None or not user.is_authenticated:
        return False
    return bool(
        getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
    )


def user_can_edit_game(user: AbstractBaseUser | None, game: Game) -> bool:
    if user is None or not user.is_authenticated:
        return False
    if user_can_edit_game_scores(user):
        return True
    return game.recorded_by_id == user.pk


def _require_notes(notes: str) -> str:
    cleaned = notes.strip()
    if not cleaned:
        raise ValidationError("Notes are required explaining why the change was made.")
    return cleaned


def _participant_row_dicts(game: Game) -> list[dict]:
    return [
        {
            "participant_result": participant,
            "player": participant.player,
            "score": participant.score,
            "result": participant.result,
            "placement": participant.placement,
        }
        for participant in game.participant_results.select_related("player").order_by(
            "pk"
        )
    ]


def _game_snapshot(
    game: Game,
    *,
    rows: list[dict] | None = None,
    location: Location | None | object = _UNCHANGED,
    double_weight: int | object = _UNCHANGED,
    played_on: date | object = _UNCHANGED,
) -> dict[str, Any]:
    if rows is None:
        rows = _participant_row_dicts(game)
    resolved_location = game.location if location is _UNCHANGED else location
    resolved_double_weight = (
        game.double_weight if double_weight is _UNCHANGED else double_weight
    )
    resolved_played_on = game.played_on if played_on is _UNCHANGED else played_on
    participants = sorted(
        [
            {
                "player_id": row["player"].pk,
                "display_name": row["player"].display_label,
                "score": row["score"],
                "result": row["result"],
                "placement": row["placement"],
            }
            for row in rows
        ],
        key=lambda participant: (
            participant["placement"] if participant["placement"] is not None else 9999,
            participant["player_id"],
        ),
    )
    return {
        "game_type_code": game.game_type_code,
        "played_on": resolved_played_on.isoformat(),
        "player_count": game.player_count,
        "score_type": game.score_type,
        "double_weight": resolved_double_weight,
        "half_weight": game.half_weight,
        "location": (
            {"id": resolved_location.pk, "name": resolved_location.name}
            if resolved_location
            else None
        ),
        "participants": participants,
    }


def _compute_participant_updates(
    game: Game,
    *,
    score_updates: dict[int, int] | None = None,
) -> tuple[list[dict], int, int, bool]:
    participants = list(
        game.participant_results.select_related("player").order_by("pk")
    )
    if not participants:
        raise ValidationError("Game has no participant results to recalculate.")

    updates = score_updates or {}
    unknown_players = sorted(set(updates) - {row.player_id for row in participants})
    if unknown_players:
        raise ValidationError(
            "Score updates include players who are not in this game: "
            + ", ".join(str(player_id) for player_id in unknown_players)
        )

    rows = _participant_row_dicts(game)
    before = {
        row["participant_result"].pk: {
            "score": row["score"],
            "result": row["result"],
            "placement": row["placement"],
        }
        for row in rows
    }
    old_double_weight = game.double_weight

    for row in rows:
        player_id = row["player"].pk
        if player_id in updates:
            row["score"] = updates[player_id]

    assign_results_from_scores(rows, game.game_type_code)
    new_double_weight = compute_double_weight(rows, game.game_type_code)

    participants_updated = 0
    for row in rows:
        participant = row["participant_result"]
        previous = before[participant.pk]
        if (
            previous["score"] != row["score"]
            or previous["result"] != row["result"]
            or previous["placement"] != row["placement"]
        ):
            participants_updated += 1

    double_weight_changed = old_double_weight != new_double_weight
    return rows, new_double_weight, participants_updated, double_weight_changed


def _save_participant_updates(
    game: Game,
    *,
    rows: list[dict],
    new_double_weight: int,
    double_weight_changed: bool,
) -> None:
    for row in rows:
        participant = row["participant_result"]
        participant.score = row["score"]
        participant.result = row["result"]
        participant.placement = row["placement"]
        participant.save(update_fields=["score", "result", "placement"])

    if double_weight_changed:
        game.double_weight = new_double_weight
        game.save(update_fields=["double_weight"])

    game.validate_participant_results()


def _build_change_log(
    *,
    game: Game,
    user: AbstractBaseUser,
    notes: str,
    old_snapshot: dict[str, Any],
    new_snapshot: dict[str, Any],
) -> GameScoreChangeLog | None:
    if old_snapshot == new_snapshot:
        return None
    return GameScoreChangeLog(
        game=game,
        changed_by=user,
        notes=notes,
        old_snapshot=old_snapshot,
        new_snapshot=new_snapshot,
    )


@transaction.atomic
def apply_game_edits(
    *,
    game: Game,
    user: AbstractBaseUser,
    notes: str,
    score_updates: dict[int, int] | None = None,
    new_location: Location | None | object = _UNCHANGED,
    new_played_on: date | object = _UNCHANGED,
    dry_run: bool = False,
) -> RecalculateSummary:
    notes = _require_notes(notes)
    if not user_can_edit_game(user, game):
        raise ValidationError("You do not have permission to edit this game.")

    updates = score_updates or {}
    location_changed = new_location is not _UNCHANGED and game.location != new_location
    date_changed = new_played_on is not _UNCHANGED and game.played_on != new_played_on

    if not updates and not location_changed and not date_changed:
        raise ValidationError(
            "Change at least one score, the date, or the location before saving."
        )

    old_snapshot = _game_snapshot(game)
    participants_updated = 0
    double_weight_changed = False
    rows: list[dict] | None = None
    new_double_weight = game.double_weight

    if updates:
        rows, new_double_weight, participants_updated, double_weight_changed = (
            _compute_participant_updates(game, score_updates=updates)
        )

    resolved_location = (
        new_location if new_location is not _UNCHANGED else game.location
    )
    resolved_played_on = (
        new_played_on if new_played_on is not _UNCHANGED else game.played_on
    )
    new_snapshot = _game_snapshot(
        game,
        rows=rows,
        location=resolved_location,
        double_weight=new_double_weight,
        played_on=resolved_played_on,
    )
    log = _build_change_log(
        game=game,
        user=user,
        notes=notes,
        old_snapshot=old_snapshot,
        new_snapshot=new_snapshot,
    )

    if dry_run:
        transaction.set_rollback(True)
        return RecalculateSummary(
            game=game,
            log=log,
            participants_updated=participants_updated,
            double_weight_changed=double_weight_changed,
            location_changed=location_changed,
            date_changed=date_changed,
        )

    if updates:
        _save_participant_updates(
            game,
            rows=rows,
            new_double_weight=new_double_weight,
            double_weight_changed=double_weight_changed,
        )

    if location_changed:
        game.location = new_location
        game.save(update_fields=["location"])

    if date_changed:
        game.played_on = new_played_on
        game.save(update_fields=["played_on"])

    if log is not None:
        log.save()

    return RecalculateSummary(
        game=game,
        log=log,
        participants_updated=participants_updated,
        double_weight_changed=double_weight_changed,
        location_changed=location_changed,
        date_changed=date_changed,
    )


@transaction.atomic
def recalculate_game_results(
    *,
    game: Game,
    user: AbstractBaseUser,
    notes: str,
    score_updates: dict[int, int] | None = None,
    dry_run: bool = False,
) -> RecalculateSummary:
    notes = _require_notes(notes)
    if not user_can_edit_game(user, game):
        raise ValidationError("You do not have permission to edit this game.")

    old_snapshot = _game_snapshot(game)
    rows, new_double_weight, participants_updated, double_weight_changed = (
        _compute_participant_updates(game, score_updates=score_updates)
    )
    new_snapshot = _game_snapshot(game, rows=rows, double_weight=new_double_weight)
    log = _build_change_log(
        game=game,
        user=user,
        notes=notes,
        old_snapshot=old_snapshot,
        new_snapshot=new_snapshot,
    )

    if dry_run:
        transaction.set_rollback(True)
        return RecalculateSummary(
            game=game,
            log=log,
            participants_updated=participants_updated,
            double_weight_changed=double_weight_changed,
        )

    if log is None:
        return RecalculateSummary(
            game=game,
            log=None,
            participants_updated=0,
            double_weight_changed=False,
        )

    _save_participant_updates(
        game,
        rows=rows,
        new_double_weight=new_double_weight,
        double_weight_changed=double_weight_changed,
    )
    log.save()
    return RecalculateSummary(
        game=game,
        log=log,
        participants_updated=participants_updated,
        double_weight_changed=double_weight_changed,
    )


@transaction.atomic
def change_game_score(
    *,
    game: Game,
    user: AbstractBaseUser,
    player: GroupPlayer,
    new_score: int,
    notes: str,
    new_location: Location | None | object = _UNCHANGED,
    dry_run: bool = False,
) -> RecalculateSummary:
    if player.group_id != game.group_id:
        raise ValidationError("Player must belong to the same group as the game.")
    return apply_game_edits(
        game=game,
        user=user,
        notes=notes,
        score_updates={player.pk: new_score},
        new_location=new_location,
        dry_run=dry_run,
    )
