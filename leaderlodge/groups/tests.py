from unittest.mock import MagicMock

from django.test import TestCase

from leaderlodge.groups.names import disambiguate_labels


def _player(pk: int, first: str, last: str, *, group_id: int = 1) -> MagicMock:
    """Build a minimal GroupPlayer mock with linked_user set."""
    p = MagicMock()
    p.pk = pk
    p.group_id = group_id
    p.is_team = False
    p.linked_user_id = pk
    p.linked_user = MagicMock()
    p.linked_user.first_name = first
    p.linked_user.last_name = last
    # display_label fallback (used for guests/teams; not exercised here)
    p.display_label = f"{first} {last[0]}" if first and last else first or "?"
    return p


def _guest(pk: int, display_name: str, *, group_id: int = 1) -> MagicMock:
    """Build a guest player mock (no linked_user)."""
    p = MagicMock()
    p.pk = pk
    p.group_id = group_id
    p.is_team = False
    p.linked_user_id = None
    p.linked_user = None
    p.display_label = display_name
    return p


# ---------------------------------------------------------------------------
# Disambiguation case table
#
# Each row: (player_a, player_b, expected_label_a, expected_label_b)
#
# Rule summary:
#   - Unique first name in the group -> show first name only
#   - Shared first name -> show 1 uppercase char of last name
#   - Shared first + 1 last char -> show 2 uppercase chars of last name
#   - Shared first + 2 last chars -> show 3 uppercase chars of last name
#   - Shared first + 3 last chars (base) -> try suffix (Jr, Sr, II ...); if
#     suffix uniquely differs, show "First Suffix"; otherwise best effort 3 chars
# ---------------------------------------------------------------------------

CASES = [
    # Different first names: unique in group, no last initial needed
    (
        _player(1, "John", "Apple"),
        _player(2, "Jane", "Apple"),
        "John",
        "Jane",
    ),
    # Same first name, first chars of last differ: show 1 char
    (
        _player(1, "John", "Apple"),
        _player(2, "John", "Berry"),
        "John A",
        "John B",
    ),
    # Same first name, first char same, second char differs: show 2 chars
    (
        _player(1, "John", "Card"),
        _player(2, "John", "Cord"),
        "John CA",
        "John CO",
    ),
    # Same first name, first 2 chars same, third char differs: show 3 chars
    (
        _player(1, "John", "Cord"),
        _player(2, "John", "Cobb"),
        "John COR",
        "John COB",
    ),
    # Same first name, first 3 chars same: best effort (show 3 chars, labels match)
    (
        _player(1, "John", "Card"),
        _player(2, "John", "Cart"),
        "John CAR",
        "John CAR",
    ),
    # Suffix: same first name, same base last, different suffix -> show suffix only
    (
        _player(1, "John", "Card Sr"),
        _player(2, "John", "Card Jr"),
        "John Sr",
        "John Jr",
    ),
]


class DisambiguateLabelsTests(TestCase):
    def _labels(self, a, b):
        result = disambiguate_labels([a, b])
        return result[a.pk], result[b.pk]

    def test_different_first_names_show_first_only(self):
        a, b, ea, eb = CASES[0]
        self.assertEqual(self._labels(a, b), (ea, eb))

    def test_same_first_last_char_differs_shows_1_char(self):
        a, b, ea, eb = CASES[1]
        self.assertEqual(self._labels(a, b), (ea, eb))

    def test_same_first_1_last_char_same_shows_2_chars(self):
        a, b, ea, eb = CASES[2]
        self.assertEqual(self._labels(a, b), (ea, eb))

    def test_same_first_2_last_chars_same_shows_3_chars(self):
        a, b, ea, eb = CASES[3]
        self.assertEqual(self._labels(a, b), (ea, eb))

    def test_same_first_3_last_chars_same_best_effort(self):
        a, b, ea, eb = CASES[4]
        self.assertEqual(self._labels(a, b), (ea, eb))

    def test_same_first_same_base_last_uses_suffix(self):
        a, b, ea, eb = CASES[5]
        self.assertEqual(self._labels(a, b), (ea, eb))

    def test_all_cases_via_table(self):
        """Drive every row in CASES through the same assertion."""
        for i, (a, b, ea, eb) in enumerate(CASES):
            with self.subTest(case=i):
                self.assertEqual(self._labels(a, b), (ea, eb))

    def test_three_players_same_first_mixed_last(self):
        """Three Johns: T unique at 1 char; Saxon and Sabre share 'SA' so expand to 3."""
        a = _player(1, "John", "Taylor")
        b = _player(2, "John", "Saxon")
        c = _player(3, "John", "Sabre")
        result = disambiguate_labels([a, b, c])
        self.assertEqual(result[a.pk], "John T")
        self.assertEqual(result[b.pk], "John SAX")
        self.assertEqual(result[c.pk], "John SAB")

    def test_guest_player_uses_display_label(self):
        a = _player(1, "John", "Smith")
        g = _guest(99, "Alice")
        result = disambiguate_labels([a, g])
        self.assertEqual(result[a.pk], "John")
        self.assertEqual(result[g.pk], "Alice")

    def test_same_first_name_in_different_groups_no_initial(self):
        """Cross-group first-name overlap must not force a last initial."""
        a = _player(1, "Nancy", "Manpearl", group_id=10)
        b = _player(2, "Nancy", "Miller", group_id=20)
        result = disambiguate_labels([a, b])
        self.assertEqual(result[a.pk], "Nancy")
        self.assertEqual(result[b.pk], "Nancy")

    def test_same_first_name_same_group_still_disambiguates(self):
        a = _player(1, "Nancy", "Manpearl", group_id=10)
        b = _player(2, "Nancy", "Miller", group_id=10)
        c = _player(3, "Nancy", "Other", group_id=20)
        result = disambiguate_labels([a, b, c])
        self.assertEqual(result[a.pk], "Nancy MA")
        self.assertEqual(result[b.pk], "Nancy MI")
        self.assertEqual(result[c.pk], "Nancy")
