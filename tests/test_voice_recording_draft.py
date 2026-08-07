import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from leaderlodge.games.models import Game
from leaderlodge.games.scoring import assign_results_from_scores
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.games.voice_draft import parse_recording_transcript
from leaderlodge.groups.location_geo import LocationGeo
from leaderlodge.groups.locations import get_or_create_location
from leaderlodge.groups.services import add_guest_player, create_group_with_owner
from leaderlodge.insights.providers.base import InsightCompletion


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.fixture
def voice_group(user):
    group = create_group_with_owner(user=user, name="Voice Club")
    # Avoid overlapping the owner username "david" (ambiguous with "David").
    for name in ("Nancy", "Jan", "Sara", "Pat"):
        add_guest_player(group=group, display_name=name)
    return group


def _completion(payload: dict) -> InsightCompletion:
    return InsightCompletion(
        text=json.dumps(payload),
        input_tokens=10,
        output_tokens=20,
        model_api_name="gpt-4o-mini",
        provider="openai",
    )


def _record_pickleball(user, group, *, score_type, location=None, scores=(11, 7)):
    players = list(group.players.order_by("pk"))
    rows = [
        {"player": players[0], "score": scores[0]},
        {"player": players[1], "score": scores[1]},
    ]
    assign_results_from_scores(rows, "pickleball")
    return record_game(
        user=user,
        group=group,
        game_type_code="pickleball",
        played_on=timezone.localdate(),
        location=location,
        score_type=score_type,
        participants=[
            ParticipantInput(
                player=row["player"],
                score=row["score"],
                result=row["result"],
                placement=row["placement"],
            )
            for row in rows
        ],
    )


@pytest.mark.django_db
@patch("leaderlodge.games.voice_draft.complete_insight")
def test_parse_recording_resolves_sides_and_rally(mock_complete, voice_group, user):
    mock_complete.return_value = _completion(
        {
            "game_type_code": "pickleball",
            "score_type": "rally",
            "location_name": None,
            "sides": [
                {"names": ["Nancy", "Pat"], "score": 11},
                {"names": ["Jan", "Sara"], "score": 9},
            ],
        }
    )
    location = get_or_create_location(
        library=voice_group.location_library,
        name="Court A",
        geo=LocationGeo(
            place_id="place-court-a",
            lat=37.0,
            lon=-122.0,
            street_address="1 Court St",
        ),
    )
    _record_pickleball(user, voice_group, score_type="rally", location=location)

    draft = parse_recording_transcript(
        group=voice_group,
        transcript="Pickleball Nancy plus Pat 11 vs Jan plus Sara 9 rally",
        user=user,
        model_slug="gpt-4o-mini",
        default_game_type_code="pickleball",
    )

    assert draft["game_type_code"] == "pickleball"
    assert draft["score_type"] == "rally"
    assert draft["location_name"] == "Court A"
    assert any("last location" in w.lower() for w in draft["warnings"])
    assert len(draft["sides"]) == 2
    assert draft["sides"][0]["score"] == 11
    assert draft["sides"][0]["players"][0]["player_id"]
    assert draft["sides"][0]["players"][1]["player_id"]
    assert draft["sides"][1]["score"] == 9
    assert not draft["ambiguities"]


@pytest.mark.django_db
@patch("leaderlodge.games.voice_draft.complete_insight")
def test_parse_recording_defaults_score_type_from_last_game(
    mock_complete, voice_group, user
):
    mock_complete.return_value = _completion(
        {
            "game_type_code": "pickleball",
            "score_type": None,
            "location_name": None,
            "sides": [
                {"names": ["Pat"], "score": 11},
                {"names": ["Nancy"], "score": 8},
            ],
        }
    )
    _record_pickleball(user, voice_group, score_type="rally")

    draft = parse_recording_transcript(
        group=voice_group,
        transcript="Pat 11 Nancy 8",
        user=user,
        model_slug="gpt-4o-mini",
        default_game_type_code="pickleball",
    )

    assert draft["score_type"] == "rally"
    assert any("score type" in w.lower() for w in draft["warnings"])


@pytest.mark.django_db
@patch("leaderlodge.games.voice_draft.complete_insight")
def test_parse_recording_ambiguous_player_becomes_guest(
    mock_complete, voice_group, user
):
    add_guest_player(group=voice_group, display_name="Alex Smith")
    add_guest_player(group=voice_group, display_name="Alex Jones")
    mock_complete.return_value = _completion(
        {
            "game_type_code": "pickleball",
            "score_type": "traditional",
            "location_name": None,
            "sides": [
                {"names": ["Alex"], "score": 11},
                {"names": ["Nancy"], "score": 9},
            ],
        }
    )

    draft = parse_recording_transcript(
        group=voice_group,
        transcript="Alex 11 vs Nancy 9",
        user=user,
        model_slug="gpt-4o-mini",
        default_game_type_code="pickleball",
    )

    alex_side = draft["sides"][0]["players"][0]
    assert alex_side["ambiguous"] is True
    assert alex_side["guest_name"] == "Alex"
    assert not alex_side["player_id"]
    assert draft["ambiguities"]
    assert any("Ambiguous" in msg for msg in draft["ambiguities"])


@pytest.mark.django_db
@patch("leaderlodge.games.voice_draft.complete_insight")
def test_parse_recording_title_cases_unmatched_guest_name(
    mock_complete, voice_group, user
):
    mock_complete.return_value = _completion(
        {
            "score_type": "rally",
            "location_name": None,
            "sides": [
                {"names": ["lucas", "hudson"], "score": 11},
                {"names": ["johnathan", "aurora"], "score": 5},
            ],
        }
    )

    draft = parse_recording_transcript(
        group=voice_group,
        transcript="lucas and hudson 11 vs johnathan and aurora 5",
        user=user,
        model_slug="gpt-4o-mini",
        default_game_type_code="pickleball",
    )

    names = [
        player["guest_name"] or player["label"]
        for side in draft["sides"]
        for player in side["players"]
        if not player["player_id"]
    ]
    assert "Johnathan" in names
    assert "johnathan" not in names
    assert all(name[:1].isupper() for name in names if name)


@pytest.mark.django_db
@patch("leaderlodge.games.voice_draft.complete_insight")
def test_parse_recording_keeps_selected_game_and_warns_on_above_fields(
    mock_complete, voice_group, user
):
    mock_complete.return_value = _completion(
        {
            "mentioned_game_type_code": "dominos",
            "mentioned_group": "manpearl",
            "mentioned_date": "8/3/2026",
            "score_type": "traditional",
            "location_name": None,
            "sides": [
                {"names": ["Lucas"], "score": 11},
                {"names": ["Amelia"], "score": 0},
            ],
        }
    )

    draft = parse_recording_transcript(
        group=voice_group,
        transcript="Lucas 11 vs Amelia 0 on 8/3/2026 traditional in group manpearl dominos",
        user=user,
        model_slug="gpt-4o-mini",
        default_game_type_code="pickleball",
    )

    assert draft["game_type_code"] == "pickleball"
    assert draft["score_type"] == "traditional"
    assert any("Date played above" in msg for msg in draft["ambiguities"])
    assert any("Group above" in msg for msg in draft["ambiguities"])
    assert any("Game above" in msg for msg in draft["ambiguities"])


@override_settings(INSIGHTS_ENABLED=True, OPENAI_API_KEY="test-key")
@pytest.mark.django_db
@patch("leaderlodge.games.voice_draft.complete_insight")
def test_parse_recording_endpoint_returns_draft(
    mock_complete, client, voice_group, user
):
    mock_complete.return_value = _completion(
        {
            "game_type_code": "pickleball",
            "score_type": "rally",
            "location_name": None,
            "sides": [
                {"names": ["Pat"], "score": 11},
                {"names": ["Nancy"], "score": 9},
            ],
        }
    )
    client.force_login(user)
    response = client.post(
        reverse("games:parse_recording"),
        data=json.dumps(
            {
                "group": voice_group.pk,
                "transcript": "Pickleball Pat 11 vs Nancy 9 rally",
                "game_type_code": "pickleball",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft"]["game_type_code"] == "pickleball"
    assert payload["draft"]["sides"][0]["score"] == 11
    assert Game.objects.count() == 0


@override_settings(INSIGHTS_ENABLED=False, OPENAI_API_KEY="", GOOGLE_AI_API_KEY="")
@pytest.mark.django_db
def test_parse_recording_endpoint_disabled_when_insights_off(client, voice_group, user):
    client.force_login(user)
    response = client.post(
        reverse("games:parse_recording"),
        data=json.dumps(
            {
                "group": voice_group.pk,
                "transcript": "Pickleball David 11 vs Nancy 9",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 503


@override_settings(INSIGHTS_ENABLED=True, OPENAI_API_KEY="test-key")
@pytest.mark.django_db
def test_record_game_page_includes_voice_controls(client, voice_group, user):
    client.force_login(user)
    response = client.get(
        reverse("games:create"),
        {"group": voice_group.pk, "type": "pickleball"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "data-game-record-voice" in content
    assert "data-parse-recording-url" in content
    assert "AI game entry" in content
    assert (
        'data-voice-title-open="Speak or type players, teams, score, location, score type"'
        in content
    )
    assert 'aria-label="Parse"' in content
    assert "bi-check-lg" in content
    assert "bi-stars" in content
    assert "game-record-voice-panel" in content
    assert "game-record-voice-body" not in content
    assert "ll-field-hint-input" in content
    assert "data-voice-mic" not in content
    assert "Fill form" not in content
    voice_idx = content.index("data-game-record-voice")
    location_idx = content.index('name="location_name"')
    assert voice_idx < location_idx
