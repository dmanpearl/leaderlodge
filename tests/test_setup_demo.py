from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from io import StringIO

from leaderlodge.games.models import Game
from leaderlodge.groups.demo import DEMO_GROUP_NAME, demo_seed_paths
from leaderlodge.groups.models import Group


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="admin",
        password="test-pass-123",
        email="admin@example.com",
    )


@pytest.mark.django_db
def test_setup_demo_creates_group_and_imports(superuser, settings):
    if not all(path.is_file() for _, path in demo_seed_paths(settings.BASE_DIR)):
        pytest.skip("Demo seed files not present")

    stdout = StringIO()
    call_command("setup_demo", stdout=stdout)

    group = Group.objects.get(name=DEMO_GROUP_NAME)
    assert group.is_demo is True
    assert group.created_by_id == superuser.pk
    assert Game.objects.filter(group=group).exists()
    assert "is_demo=True" in stdout.getvalue() or "already exists" in stdout.getvalue()


@pytest.mark.django_db
def test_setup_demo_dry_run(superuser, settings, tmp_path):
    stdout = StringIO()
    call_command("setup_demo", "--dry-run", stdout=stdout)
    output = stdout.getvalue()

    assert Group.objects.filter(name=DEMO_GROUP_NAME).count() == 0
    assert "Dry run" in output
    assert "Would create group" in output or "Would update group" in output


@pytest.mark.django_db
def test_setup_demo_idempotent(superuser, settings):
    if not all(path.is_file() for _, path in demo_seed_paths(settings.BASE_DIR)):
        pytest.skip("Demo seed files not present")

    call_command("setup_demo", stdout=StringIO())
    first_count = Game.objects.filter(group__name=DEMO_GROUP_NAME).count()

    stdout = StringIO()
    call_command("setup_demo", stdout=stdout)
    second_count = Game.objects.filter(group__name=DEMO_GROUP_NAME).count()

    assert second_count == first_count
    assert "skipped" in stdout.getvalue().lower() or "already exists" in stdout.getvalue()
