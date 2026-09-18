from leaderlodge.games.snapshot_diff import format_snapshot_diff, format_snapshot_pretty


def test_format_snapshot_diff_empty_score_type():
    old_snapshot = {"score_type": "", "participants": []}
    new_snapshot = {"score_type": "chinese_mcr", "participants": []}

    diff = format_snapshot_diff(old_snapshot, new_snapshot)

    assert diff == "score_type: (empty) to chinese_mcr"


def test_format_snapshot_diff_scalar_and_participant_changes():
    old_snapshot = {
        "played_on": "2026-06-30",
        "location": {"id": 1, "name": "Clubhouse"},
        "participants": [
            {
                "player_id": 10,
                "display_name": "Elena",
                "score": 11,
                "result": "played",
                "placement": 1,
            },
            {
                "player_id": 20,
                "display_name": "Lucy",
                "score": 8,
                "result": "played",
                "placement": 2,
            },
        ],
    }
    new_snapshot = {
        "played_on": "2026-07-01",
        "location": {"id": 2, "name": "Preston"},
        "participants": [
            {
                "player_id": 10,
                "display_name": "Elena",
                "score": 15,
                "result": "win",
                "placement": 1,
            },
            {
                "player_id": 30,
                "display_name": "Harper",
                "score": 12,
                "result": "played",
                "placement": 3,
            },
            {
                "player_id": 31,
                "display_name": "Owen",
                "score": 12,
                "result": "played",
                "placement": 3,
            },
        ],
    }

    diff = format_snapshot_diff(old_snapshot, new_snapshot)

    assert "played_on: 2026-06-30 to 2026-07-01" in diff
    assert "location: Clubhouse to Preston" in diff
    assert "Elena: score 11 to 15, result played to win" in diff
    assert "Removed: Lucy" in diff
    assert "Added side: Harper+Owen" in diff


def test_format_snapshot_diff_delete_event():
    old_snapshot = {
        "participants": [
            {
                "player_id": 1,
                "display_name": "Alice",
                "score": 10,
                "result": "win",
                "placement": 1,
            }
        ]
    }

    diff = format_snapshot_diff(old_snapshot, {})

    assert diff == "Game deleted\nRemoved: Alice"


def test_format_snapshot_diff_location_pin_change():
    old_snapshot = {
        "location": {"id": 1, "name": "Kitchen", "lat": None, "lon": None},
        "participants": [],
    }
    new_snapshot = {
        "location": {
            "id": 1,
            "name": "Kitchen",
            "lat": 34.0522,
            "lon": -118.2437,
        },
        "participants": [],
    }

    diff = format_snapshot_diff(old_snapshot, new_snapshot)

    assert diff == "location pin: (none) to 34.0522, -118.2437"


def test_format_snapshot_diff_no_changes():
    snapshot = {
        "played_on": "2026-06-30",
        "location": {"id": 1, "name": "Kitchen", "lat": 34.0, "lon": -118.0},
        "participants": [
            {
                "player_id": 1,
                "display_name": "Alice",
                "score": 10,
                "result": "win",
                "placement": 1,
            }
        ],
    }

    assert format_snapshot_diff(snapshot, snapshot) == "(no differences)"


def test_format_snapshot_pretty_renders_game_state():
    snapshot = {
        "group": {"id": 1, "name": "Dom Club"},
        "game_type_code": "dominos",
        "played_on": "2026-06-30",
        "score_type": "",
        "double_weight": 2,
        "half_weight": 1,
        "location": {
            "id": 1,
            "name": "Kitchen",
            "lat": 34.0522,
            "lon": -118.2437,
        },
        "participants": [
            {
                "player_id": 10,
                "display_name": "Elena",
                "score": 35,
                "result": "win",
                "placement": 1,
            },
            {
                "player_id": 20,
                "display_name": "Lucy",
                "score": 25,
                "result": "played",
                "placement": 2,
            },
        ],
    }

    pretty = format_snapshot_pretty(snapshot)

    assert "Group: Dom Club" in pretty
    assert "Game: Dominos" in pretty
    assert "Date played: Jun 30, 2026" in pretty
    assert "Location: Kitchen (34.0522, -118.2437)" in pretty
    assert "Game length: Double" in pretty
    assert "Elena: 35 (Win)" in pretty
    assert "Lucy: 25 (Played)" in pretty


def test_format_snapshot_pretty_empty_snapshot():
    assert format_snapshot_pretty({}) == ""
