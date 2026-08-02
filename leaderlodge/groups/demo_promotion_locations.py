"""Location name remapping for promoting games from a source group into Demo.

Companion to `demo_promotion_names.py` (see that module for the player name
policy and the reasoning behind hand-maintained, permanent mapping files).

Policy: only remap locations that reveal someone's personal home/place (e.g.
"Nancy's House") or otherwise carry personal information. When remapping,
strip personal details entirely rather than trying to anonymize them in
place: birthdays, guest/companion lists ("visited so-and-so"), medical or
other personal notes all get removed, keeping just the underlying
venue/place name. Business names, addresses, and real geocoded coordinates
are left untouched for everything not listed here. If a remapped location
ever has latitude/longitude set, blur it (round to 2 decimal places, about
half a mile to a mile of imprecision) rather than dropping it, since the
Map view plots games by location and a fully missing coordinate drops the
game from the map entirely. Rounding keeps the pin in roughly the right
neighborhood without preserving enough precision to reverse-geocode an
exact address.

Locations with no entry here are copied through unchanged: most locations
are businesses, addresses, or generic names ("Home", a restaurant, a park)
that don't need remapping at all. This file only needs to list the
personal-information exceptions, not every location.
"""

SOURCE_GROUP_NAME = "manpearl"
DEST_GROUP_NAME = "Demo"

LOCATION_NAME_MAP: dict[str, str] = {
    # Someone's house/home, referenced by name.
    "Nancy's House": "Amelia's House",
    "Debby's House": "Aurora's House",
    "Sally": "Lucas",
    # "Ian" never appears as a game participant in the source group, so he
    # has no entry in the player name map; this is a location-only stand-in.
    "Ian's House": "Felix's House",
    # Real venue names kept; personal details (birthday, health/recovery
    # note, guest list) stripped entirely rather than name-swapped in place.
    "Venice Cucina on Nancy's 6th AA Bday": "Venice Cucina",
    "Campland, San Diego, Nancy\u2019s birthday and Parrot Head": "Campland, San Diego",
    "Gilly's, Los Gatos (visited Zach, Alize, Kristen, Kyle, Marie, Jim, Soren)": "Gilly's, Los Gatos",
}
