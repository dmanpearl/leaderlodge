# LeaderLodge Location Map

LeaderLodge stores one geographic point per group venue (`Location`),
captures coordinates while recording or editing games, and uses those
points for the Games Map, leaderboard venue filter, and Ask the Lodge
regional questions.

Locations stay per group (`LocationLibrary`). There is no shared
cross-group venue registry. Games reference a Location by foreign key;
once a venue is geocoded, every game at that venue shares the pin.

Related docs: `docs/google-places.md`, `docs/features.md`,
`docs/ask-the-lodge-capabilities.md`, `docs/ai-insights.md`.

## Table of contents

1. [Capture and geocoding](#capture-and-geocoding)
   1. [Coordinate source rule](#coordinate-source-rule)
   2. [Capture scenarios](#capture-scenarios)
   3. [Fill-in and overwrite rules](#fill-in-and-overwrite-rules)
2. [Data model](#data-model)
3. [Near me and Search on Record Game](#near-me-and-search-on-record-game)
4. [Set place map picker](#set-place-map-picker)
5. [Record Game map](#record-game-map)
6. [Location library tools](#location-library-tools)
7. [Games Map](#games-map)
   1. [Filters](#filters)
   2. [Clustering and viewport loading](#clustering-and-viewport-loading)
8. [Leaderboard venue filter](#leaderboard-venue-filter)
9. [Ask the Lodge geo tools](#ask-the-lodge-geo-tools)
10. [Map provider and shared UI](#map-provider-and-shared-ui)
11. [Privacy](#privacy)
12. [Out of scope](#out-of-scope)
13. [Future features](#future-features)

---

## Capture and geocoding

Each Location stores **exactly one** `lat` / `lon` pair. Prefer capture
when the user sets a place; reuse saved coordinates when they pick an
existing venue; never require a fresh lookup for a row that already has
coords.

### Coordinate source rule

| User action | Saved lat/lon | `geocode_source` |
|-------------|---------------|------------------|
| Picks a Places result (Near me or in-field Search) | Google place geometry | `places_lookup` or `text_search` |
| Drops a map pin | Pin coordinates | `map_pin` |
| Types a custom name after Near me with GPS available | Phone GPS | `gps` |
| City-only Near me row ("Los Angeles, CA") | Phone GPS | `gps` |
| Types a name with no Near me / Search / picker geo | None until Set place or fill-in | (blank) |
| Reuses an existing Location that already has coords | Existing saved lat/lon | unchanged |

Phone GPS is used to **discover** nearby places and as the pin when
there is no Google place point. A Places pick always prefers Google
lat/lon over the device reading.

### Capture scenarios

**At the venue:** Near me runs nearby search; selecting a place stores
name, `place_id`, address components, and Google lat/lon.

**Away from the venue (back-entry):** Prefer Search, Map pin, or Set
place. Near me remains available if the user is still near the venue;
if they pick a Places result, Google geometry is still what is saved.

**Custom name with GPS:** e.g. "Sally's House" after Near me stores
custom name + phone GPS (`geocode_source=gps`), no `place_id`.

**Reuse:** Fuzzy / autocomplete resolve to the existing Location; keep
saved coords unless `lat` is null and a geo payload fills them in.

### Fill-in and overwrite rules

| Situation | Behavior |
|-----------|----------|
| New Location, geo payload present | Write lat/lon and address fields |
| Existing Location, already has lat/lon | Keep existing coords on silent reuse |
| Existing Location, `lat IS NULL`, geo payload present | Fill coords and address fields |
| Explicit Set place / re-geocode | Set or replace coords (confirm if already set) |
| Typed name only, no geo payload | Name only; lat/lon stay null until Set place or later fill-in |

---

## Data model

Geographic fields live on `Location` (not on `Game`):

| Field | Notes |
|-------|-------|
| `lat`, `lon` | WGS84; nullable until geocoded |
| `city`, `state`, `country` | Locality, short region code, ISO alpha-2 |
| `postal_code`, `street_address` | Optional address pieces |
| `place_id` | Google Places id (silent reuse when already in library) |
| `geocode_source` | `gps`, `places_lookup`, `map_pin`, `text_search`, `manual`, … |
| `geocode_confidence`, `geocode_at` | Optional quality / timestamp |

Indexes support map/filter queries: `(lat, lon)`, `(state, city)`,
`(country, state)`, `(library, place_id)`.

Coordinates are stored at about 6 decimal places. City-only Near me rows
use phone GPS and leave `place_id` blank.

---

## Near me and Search on Record Game

On game setup / recording:

- **Near me** always uses device GPS for nearby Places search.
- **Search** (in-field magnifying glass) runs Places text search (up to
  8 results).
- Hidden geo fields travel with the name through the roster save step.
- Client: `static/js/location_lookup.js`. Details: `docs/google-places.md`.

---

## Set place map picker

Group managers can open **Set place** from Edit game, Game detail, or
the Locations list. The modal updates the **shared Location** row (all
games at that venue).

Capabilities:

- Places search by name (inline submit icon in the search field)
- Drop pin; **pin-map icon** finds nearby Places at the pin or map center
- **Crosshair icon** for device location; opens at municipality zoom when
  no pin exists yet, then street-level zoom when used
- Assign with overwrite confirmation when coords already exist
- Optional adopt Google place name

Module: `static/js/location_map.js` (assign mode). Who can use it:
same permission as rename / combine on Locations.

---

## Record Game map

Record Game includes a **Map** control that opens the same picker in
**record** mode. Confirm writes name + hidden geo onto the game form;
Near me and Search stay available beside it.

---

## Location library tools

On the group Locations page:

- Geocoded badge; row action **Set place**
- **Find duplicates:** fuzzy name pairs and same-`place_id` pairs;
  merge via existing combine (keeper keeps geo; null keeper can copy
  from source)
- Name-extension pairs (short name vs name with a suffix) are not
  auto-suggested; manual combine remains available

Helpers: `rename_location`, `combine_locations`,
`find_duplicate_location_pairs` in `leaderlodge/groups/locations.py`.

Interactive CLI `backfill_location_places` (human accept/reject) is
documented in `docs/google-places.md`. Unattended bulk auto-geocode is
not supported.

---

## Games Map

Authenticated members (and anonymous Demo when demo mode is on) open
`/games/map/` to browse geocoded venues with filters and clusters.

- Page: `games:map`
- GeoJSON: `GET /api/map/locations/` (`map_locations`)
- Code: `leaderlodge/games/map_data.py`, `map_views.py`,
  `templates/games/game_map.html`, `static/js/game_map.js`,
  `game_map_filters.js`

Empty states cover no groups, missing Maps key, ungeocoded libraries,
and no matches for current filters. Pin popups link to Location detail
and to the Games list filtered by that venue.

### Filters

| Filter | UI | Notes |
|--------|----|-------|
| Group | Single select | Visible groups for the user |
| Game | Single select | Types with games in the group |
| Player | Single select | Players who appear in filtered games |
| Period | Year / month / quick range / custom | Same period helpers as Games and Leaderboards |
| Country | Single select | Cascades state and city options |
| State | Single select | Narrowed by country when set |
| City | Text + datalist | Narrowed by country and/or state |
| Location | Fuzzy type-ahead | Venue names with geocoded games |

Country, state, and city cascade client-side from an embedded tree of
geocoded venues (`map_geo_cascade_tree`). Apply submits the form and
reloads the map with the filter query in the URL (bookmarkable).

Backend filter parameters match the form fields (`country`, `state`,
`city`, `location_name`, plus group / game / player / period).

### Clustering and viewport loading

- **Clustering:** Supercluster in the browser (CDN). Zoom/pan redraws
  cluster bubbles vs individual pins.
- **Viewport loading (bbox refetch):** after the initial fit to all
  filtered pins, further pan/zoom requests
  `/api/map/locations/?…&bbox=lon_min,lat_min,lon_max,lat_max` (padded).
  Only pins inside that visible rectangle (plus margin) are returned
  and reclustered. Status text shows how many places are in view.

Markers use classic `google.maps.Marker`.

---

## Leaderboard venue filter

The leaderboard page Location select filters rankings by `location_id`
(venues that have games for the current game type). Ranking service
support was already present; the UI is wired.

City / state / country filters on the leaderboard page are not shipped;
use Games Map or Ask for regional views.

---

## Ask the Lodge geo tools

Validated tools (not free-form LLM filters):

| Tool | Purpose |
|------|---------|
| `query_location_leaderboard` | Leaders at one named venue |
| `query_region_leaderboard` | Leaders in a city and/or state; `exclude=true` for outside that region |
| `query_play_locations` | Group venues by games played (optional city/state / exclude) |
| `query_player_play_locations` | One player's games by state, city, or venue (includes unknown geo bucket) |

Regional answers only include venues with matching city/state filled.
Thin coverage is surfaced via `coverage_thin` / `coverage_note`. Matchup
insight JSON includes `location_city` / `location_state` when present.

In-app examples: `/insights/ask/examples/`. Capability details:
`docs/ask-the-lodge-capabilities.md`.

---

## Map provider and shared UI

Google Maps JavaScript API plus Places API (New) and Geocoding for pin
lookup. Browser key: `GOOGLE_PLACES_API_KEY`.

Shared picker module: `static/js/location_map.js` (assign / record
modes). Games Map viewer is separate (`game_map.js`) and uses the
GeoJSON API above.

---

## Privacy

Locations are per-group. Members see their groups' places. Anonymous
users only see Demo group locations when demo mode is on. Staff can
inspect locations in Admin.

v1 stores precise coordinates when GPS or pin is used (including
homes). Optional display fuzzing or street-number stripping is not
implemented.

---

## Out of scope

- Cross-group shared venue registry
- Indoor vs outdoor classification
- Arbitrary polygon / "west side of LA" geo queries
- Native iOS / Android map apps
- Overwriting coords on every silent reuse of a geocoded Location
- Unattended bulk backfill from name alone (no human confirm)

---

## Future features

Possible later work (not scheduled):

- **Server-side clustering:** API returns pre-aggregated cluster
  centroids at a given zoom when client Supercluster is too slow
  (roughly hundreds of visible pins).
- **Caching GeoJSON:** cache `/api/map/locations/` by group + filters +
  bbox; invalidate on new games or location geocode changes.
- **Custom game-type map pins:** HTML / `AdvancedMarkerElement` pins
  with game icons and richer hover / cluster styling (cancelled as a
  ship requirement; classic markers remain).
- **Leaderboard city / state / country filters:** cascade similar to
  Games Map, expanding to matching venue ids.
- **Street-number stripping** for display while keeping precise pins.
