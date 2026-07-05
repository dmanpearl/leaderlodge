from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import transaction

from leaderlodge.games.models import Game, GameParticipantResult, GameScoreChangeLog
from leaderlodge.games.scoring import assign_results_from_scores, compute_double_weight
from leaderlodge.groups.models import GroupPlayer


@dataclass(frozen=True)
class RecalculateSummary:
    game: Game
    logs: list[GameScoreChangeLog]
    participants_updated: int
    double_weight_changed: bool


def user_can_edit_game_scores(user: AbstractBaseUser | None) -> bool:
    if user is None or not user.is_authenticated:
        return False
    return bool(
        getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
    )


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


@transaction.atomic
def recalculate_game_results(
    *,
    game: Game,
    user: AbstractBaseUser,
    notes: str,
    score_updates: dict[int, int] | None = None,
    change_type: str = GameScoreChangeLog.ChangeType.RECALCULATE,
    dry_run: bool = False,
) -> RecalculateSummary:
    notes = _require_notes(notes)
    if not user_can_edit_game_scores(user):
        raise ValidationError("Only staff can change game scores.")

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

    logs: list[GameScoreChangeLog] = []
    participants_updated = 0
    for row in rows:
        participant = row["participant_result"]
        previous = before[participant.pk]
        new_score = row["score"]
        new_result = row["result"]
        new_placement = row["placement"]
        score_changed = previous["score"] != new_score
        result_changed = previous["result"] != new_result
        placement_changed = previous["placement"] != new_placement
        if not (score_changed or result_changed or placement_changed):
            continue
        if (
            change_type == GameScoreChangeLog.ChangeType.SCORE_CHANGE
            and row["player"].pk not in updates
        ):
            continue
        participants_updated += 1
        logs.append(
            GameScoreChangeLog(
                game=game,
                participant_result=participant,
                player=participant.player,
                changed_by=user,
                notes=notes,
                change_type=change_type,
                old_score=previous["score"],
                new_score=new_score,
                old_result=previous["result"],
                new_result=new_result,
                old_placement=previous["placement"],
                new_placement=new_placement,
                old_double_weight=old_double_weight,
                new_double_weight=new_double_weight,
            )
        )

    double_weight_changed = old_double_weight != new_double_weight
    if double_weight_changed and not logs:
        logs.append(
            GameScoreChangeLog(
                game=game,
                participant_result=None,
                player=None,
                changed_by=user,
                notes=notes,
                change_type=change_type,
                old_score=0,
                new_score=0,
                old_result="",
                new_result="",
                old_placement=None,
                new_placement=None,
                old_double_weight=old_double_weight,
                new_double_weight=new_double_weight,
            )
        )

    if dry_run:
        transaction.set_rollback(True)
        return RecalculateSummary(
            game=game,
            logs=logs,
            participants_updated=participants_updated,
            double_weight_changed=double_weight_changed,
        )

    for row in rows:
        participant = row["participant_result"]
        participant.score = row["score"]
        participant.result = row["result"]
        participant.placement = row["placement"]
        participant.save(update_fields=["score", "result", "placement"])

    if double_weight_changed:
        game.double_weight = new_double_weight
        game.save(update_fields=["double_weight"])

    if logs:
        GameScoreChangeLog.objects.bulk_create(logs)

    game.validate_participant_results()
    return RecalculateSummary(
        game=game,
        logs=logs,
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
    dry_run: bool = False,
) -> RecalculateSummary:
    if player.group_id != game.group_id:
        raise ValidationError("Player must belong to the same group as the game.")
    return recalculate_game_results(
        game=game,
        user=user,
        notes=notes,
        score_updates={player.pk: new_score},
        change_type=GameScoreChangeLog.ChangeType.SCORE_CHANGE,
        dry_run=dry_run,
    )
