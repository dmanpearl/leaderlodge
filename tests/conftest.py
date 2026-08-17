import pytest


def pytest_collection_modifyitems(config, items):
    """Use savepoint rollbacks instead of full DB flushes between tests."""
    for item in items:
        if item.get_closest_marker("django_db") is not None:
            item.add_marker(pytest.mark.django_db(transaction=True))


@pytest.fixture(autouse=True)
def _clear_geoip_cache():
    """Prevent cached IP lookups from leaking geo data between tests."""
    from leaderlodge.core.geoip import lookup_ip

    lookup_ip.cache_clear()
    yield
    lookup_ip.cache_clear()


def edit_game_participant_post(game, **extra):
    from leaderlodge.games.reuse_players import participant_rows_for_edit_game

    rows = participant_rows_for_edit_game(game)
    post = {
        "played_on": game.played_on.isoformat(),
        "participant_player_id": [str(r.get("player_id") or "") for r in rows],
        "participant_guest_name": [r.get("guest_name") or "" for r in rows],
        "participant_teammate_player_id": [
            str(r.get("teammate_player_id") or "") for r in rows
        ],
        "participant_teammate_guest_name": [
            r.get("teammate_guest_name") or "" for r in rows
        ],
        "participant_score": [str(r["score"]) for r in rows],
    }
    post.update(extra)
    return post
