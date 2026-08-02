"""Player name remapping for promoting games from a real group into Demo.

Used by the "promote demo games" tooling that copies games from a source
group (e.g. "manpearl") into the "Demo" group so Guests see realistic,
anonymized examples. Every promoted player becomes a Guest in Demo (no
linked user, no email) under the fictional first name below.

This is a hand-maintained, permanent mapping, not a one-time snapshot. The
source group's real roster changes over time (new guests join, inactive
ones drop off), so entries here are expected to be added or edited by hand
as that happens. The promotion tool should warn and skip (not fail) any
source-group player it encounters that has no entry here, and report the
skipped names so this file can be updated.

Keys are the source player's `display_label` (the name shown in the UI,
e.g. "David" for a linked user, not the raw `display_name` field which may
be a username like "dmanpearl"). Values are the fictional Demo first name.

If two source players ever need to map to the same first name, disambiguate
with a short last initial (e.g. "Jeff M" -> "Owen T", "Jeff P" -> "Owen R"),
matching how the source group itself disambiguates duplicate first names
(see manpearl's "Jeff M" / "Jeff P").
"""

SOURCE_GROUP_NAME = "manpearl"
DEST_GROUP_NAME = "Demo"

# Players with zero recorded games in the source group as of this writing are
# intentionally omitted (nothing to promote for them): Hotmail, John, John
# Jacob, user1.
PLAYER_NAME_MAP: dict[str, str] = {
    "Nancy": "Amelia",
    "David": "Hudson",
    "Charlene": "Lucy",
    "Sally": "Lucas",
    "Debby": "Aurora",
    "Sandy": "Lily",
    "Jeff M": "Luna",
    "Karen": "Layla",
    "Sara": "Owen",
    "Susan": "Cooper",
    "Karenina": "Elena",
    # Same real person as "Karenina" above; production added a last initial
    # after this file's local dev snapshot was taken. Reuse "Elena".
    "Karenina M": "Elena",
    "Allyn": "Harper",
    "Espy": "Theo",
    "Jack": "Mason",
    "Kas": "Asher",
    "Melissa": "Carter",
    "Ray": "Ezra",
    "Candace": "Nora",
    "Clelia": "Violet",
    "Jan": "Wyatt",
    "Simon": "Ivy",
    "Zach": "Levi",
    "Terry": "Stella",
    "Jeremy": "Grayson",
    "Jordan": "Hazel",
    "Bo": "Miles",
    "Alizé": "Nova",
    "Jake": "Silas",
    "Jeff P": "Willow",
    "Scott": "Jasper",
    "Keavy": "Piper",
}
