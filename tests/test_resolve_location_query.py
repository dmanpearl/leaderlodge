import pytest
from django.contrib.auth.models import User

from leaderlodge.groups.locations import (
    get_or_create_location,
    score_location_match,
    score_location_resolve_match,
    normalize_for_fuzzy_match,
)
from leaderlodge.groups.services import create_group_with_owner
from leaderlodge.insights.tools.locations import resolve_location_query


@pytest.fixture
def user(db):
    return User.objects.create_user(username="david", password="test-pass-123")


@pytest.mark.django_db
def test_resolve_location_short_name_matches_places_label(user):
    group = create_group_with_owner(user=user, name="Test")
    full = get_or_create_location(
        library=group.location_library,
        name="Zinqué Venice, Los Angeles, CA",
    )

    for query in ("Zinque", "Zinqué", "zinque venice"):
        assert resolve_location_query(group, query).pk == full.pk


@pytest.mark.django_db
def test_resolve_location_ambiguous_shared_leading_word(user):
    from leaderlodge.groups.models import Location

    group = create_group_with_owner(user=user, name="Test")
    library = group.location_library
    # Create rows directly so get_or_create fuzzy merge cannot collapse them.
    Location.objects.create(
        library=library,
        name="Zinque Venice",
        normalized_name="zinque venice",
    )
    Location.objects.create(
        library=library,
        name="Zinque Santa Monica",
        normalized_name="zinque santa monica",
    )

    assert library.locations.count() == 2
    with pytest.raises(ValueError, match="Ambiguous location"):
        resolve_location_query(group, "Zinque")


def test_merge_score_still_rejects_short_prefix_into_longer_name():
    query = normalize_for_fuzzy_match("Zinque")
    candidate = normalize_for_fuzzy_match("Zinqué Venice, Los Angeles, CA")
    assert score_location_match(query, candidate) < 0
    assert score_location_resolve_match(query, candidate) > 0
