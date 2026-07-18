from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from leaderlodge.games.models import Game
from leaderlodge.groups.demo import DEMO_GROUP_NAME
from leaderlodge.groups.models import Group
from tests.fixtures.test_seeds import (
    EXPECTED_GAME_COUNTS,
    all_committed_test_seeds_present,
    committed_test_seed_paths,
)


@pytest.fixture
def superuser(db):
    user, created = User.objects.get_or_create(
        username="admin",
        defaults={
            "email": "admin@example.com",
            "is_superuser": True,
            "is_staff": True,
        },
    )
    if not created and not user.is_superuser:
        user.is_superuser = True
        user.is_staff = True
        user.save(update_fields=["is_superuser", "is_staff"])
    if created or not user.has_usable_password():
        user.set_password("test-pass-123")
        user.save(update_fields=["password"])
    return user


@pytest.fixture
def use_test_demo_seeds(monkeypatch):
    import leaderlodge.groups.demo as demo_module

    monkeypatch.setattr(demo_module, "demo_seed_paths", committed_test_seed_paths)


@pytest.fixture(scope="module")
def use_test_demo_seeds_module():
    import leaderlodge.groups.demo as demo_module

    original = demo_module.demo_seed_paths
    demo_module.demo_seed_paths = committed_test_seed_paths
    yield
    demo_module.demo_seed_paths = original


@pytest.fixture(scope="module")
def demo_group_seeded_once(
    django_db_setup,
    django_db_blocker,
    use_test_demo_seeds_module,
):
    if not all_committed_test_seeds_present():
        pytest.skip(
            "Test seed files not present; run tests/fixtures/build_test_seeds.py"
        )

    with django_db_blocker.unblock():
        User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "is_superuser": True,
                "is_staff": True,
            },
        )
        call_command("setup_demo", stdout=StringIO())
        yield Group.objects.get(name=DEMO_GROUP_NAME)


@pytest.mark.django_db
def test_setup_demo_creates_group_and_imports(demo_group_seeded_once):
    group = demo_group_seeded_once
    assert group.is_demo is True
    assert group.created_by.username == "admin"
    from leaderlodge.groups.demo import DEMO_GROUP_DESCRIPTION

    assert group.description == DEMO_GROUP_DESCRIPTION

    for game_type, expected in EXPECTED_GAME_COUNTS.items():
        assert (
            Game.objects.filter(group=group, game_type_code=game_type).count()
            == expected
        )


@pytest.mark.django_db
def test_setup_demo_dry_run(superuser, use_test_demo_seeds):
    if not all_committed_test_seeds_present():
        pytest.skip(
            "Test seed files not present; run tests/fixtures/build_test_seeds.py"
        )

    before_groups = Group.objects.filter(name=DEMO_GROUP_NAME).count()
    before_games = Game.objects.count()

    stdout = StringIO()
    call_command("setup_demo", "--dry-run", stdout=stdout)
    output = stdout.getvalue()

    assert Group.objects.filter(name=DEMO_GROUP_NAME).count() == before_groups
    assert Game.objects.count() == before_games
    assert "Dry run" in output
    assert (
        "Would create group" in output
        or "Would update group" in output
        or "Would import" in output
    )


@pytest.mark.django_db
def test_setup_demo_idempotent(demo_group_seeded_once):
    group = demo_group_seeded_once
    first_count = Game.objects.filter(group=group).count()

    stdout = StringIO()
    call_command("setup_demo", stdout=stdout)
    second_count = Game.objects.filter(group=group).count()

    assert second_count == first_count
    assert (
        "skipped" in stdout.getvalue().lower() or "already exists" in stdout.getvalue()
    )
