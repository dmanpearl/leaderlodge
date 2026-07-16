# LeaderLodge Location Map

Plan for displaying game-play locations as pins on a map, with rich
filtering, a map-based location picker for game recording, and AI-aware
geographic queries.

**Status: Phase 1 implemented (schema + Lookup geo save). Later phases
still planning.**

---

## Table of contents

1. [Overview](#overview)
2. [Capture scenarios (product intent)](#capture-scenarios-product-intent)
3. [Database schema changes](#database-schema-changes)
4. [Geocoding strategy](#geocoding-strategy)
5. [Phase 1 save path](#phase-1-save-path)
6. [The back-entry problem](#the-back-entry-problem)
7. [Backfill tool](#backfill-tool)
8. [Map picker - game recording](#map-picker---game-recording)
9. [Map viewer - explore by location](#map-viewer---explore-by-location)
10. [Location filters](#location-filters)
11. [Leaderboard location filters](#leaderboard-location-filters)
12. [AI integration (Ask the Lodge)](#ai-integration-ask-the-lodge)
13. [Map provider: Google Maps JS](#map-provider-google-maps-js)
14. [Custom game-type pins](#custom-game-type-pins)
15. [Shared map component](#shared-map-component)
16. [Performance and clustering](#performance-and-clustering)
17. [Privacy model](#privacy-model)
18. [Existing location tooling](#existing-location-tooling)
19. [Out of scope](#out-of-scope)
20. [Documentation and examples checklist](#documentation-and-examples-checklist)
21. [Implementation phases](#implementation-phases)

---

## Overview

The Location model already exists and is per-group (each group has its
own LocationLibrary). A Location has only a name today. The plan is to:

- Add coordinate and structured address fields to Location
- Capture one lat/lon per Location at recording time (Places geometry,
  map pin, or device GPS when there is no place point)
- Reuse saved coordinates when the user picks an existing Location
- Provide backfill tools (Admin UI required early for large existing
  libraries; CLI optional) so name-only locations still get lat/lon
- Build a map viewer with pin clustering and rich filters
- Add location filters on the leaderboard UI (service already supports
  venue filter; Ask already has `query_location_leaderboard`)
- Build an enhanced map-based picker that replaces/extends the current
  Lookup button flow
- Share a single map component between the picker and the viewer

**Guiding rule:** every Location stores one lat/lon and should end up
with the best point we can obtain. Places picks use Google geometry
(not phone GPS). Prefer capture at entry; fall back to backfill; never
require a fresh lookup when reusing a Location that already has
coordinates.

---

## Capture scenarios (product intent)

These are the recording behaviors the plan must support.

### Coordinate source rule (single lat/lon)

Each Location stores **exactly one** `lat`/`lon` pair. No separate phone
vs Google coordinate fields.

| User action | Saved lat/lon | `geocode_source` |
|-------------|---------------|------------------|
| Picks a Places result (nearby Lookup or search) | **Google** place geometry (overrides phone GPS) | `places_lookup` or `text_search` |
| Drops a map pin | Pin coordinates | `map_pin` |
| Types a custom name after Lookup (e.g. "Sally's House") with GPS available | **Phone** GPS | `gps` |
| City-only Lookup row ("Los Angeles, CA") | **Phone** GPS | `gps` |
| Types a name with no Lookup / picker geo | None (`lat` null) until fill-in or backfill | (blank) |
| Reuses an existing Location that already has coords | Existing saved lat/lon (no new lookup) | unchanged |

Phone GPS is used only to **discover** nearby places and as the pin when
there is no Google place point. A Places pick always prefers Google
lat/lon over the device reading.

Privacy of precise home coordinates is not a blocker for v1; store full
precision. Optional street-number stripping for display remains a later
nice-to-have (see Privacy).

### A. Record at the play location (typical)

User is physically at the venue and taps Lookup (or later, "Use my
location" in the map picker).

- Device GPS runs nearby search.
- User selects a place from the list: store selected **name** (place,
  city, state), `place_id`, address components, and **Google** lat/lon.
- `geocode_source=places_lookup`.

### B. Record later, away from the venue (back-entry)

User records hours or days later from somewhere else.

- Device GPS is the wrong pin if used as the venue. Prefer text search
  or (later) map pin / Places result.
- Store selected **name** plus **place or pin** lat/lon.
- `geocode_source=places_lookup`, `text_search`, or `map_pin`.

GPS Lookup remains available (see Back-entry policy) so users who are
actually still near the venue can use it; users who are elsewhere should
prefer search or map pin. If they do use Lookup and pick a Places
result, Google place lat/lon is still what is saved (same as A).

### C. Custom name while Lookup GPS is available

User runs Lookup (or has GPS), ignores the place list, and types
"Sally's House".

- Store custom name + **phone GPS** lat/lon (no Google place point).
- `geocode_source=gps`. No place_id required.
- Acceptable for homes and informal venues.

### D. Reuse an existing Location

User picks "Sally's House" (or any prior name) from autocomplete or by
typing a name that fuzzy-matches an existing row.

- Resolve to the existing Location FK (current `get_or_create_location`
  / fuzzy merge behavior).
- **Reuse saved lat/lon.** Do not call Places or overwrite coordinates.
- No new lookup unless the Location has `lat IS NULL` (see fill-in
  rules below).

### Fill-in and overwrite rules

| Situation | Behavior |
|-----------|----------|
| New Location, geo payload present | Write lat/lon and address fields |
| Existing Location, already has lat/lon | Keep existing coords; ignore new GPS/place coords on silent reuse |
| Existing Location, `lat IS NULL`, geo payload present | Fill coords and address fields (upgrade name-only row) |
| Existing Location, operator backfill or explicit re-geocode | Allowed to set or replace coords |
| Typed name only, no geo payload | Create/reuse name only; leave lat/lon null until backfill or a later fill-in |

Goal: **management system** so ungeocoded rows are visible and
backfillable; reuse never burns API calls or relocates a known venue.

---

## Database schema changes

### Fields to add to `Location`

| Field | Type | Notes |
|-------|------|-------|
| `lat` | `FloatField(null=True, blank=True)` | WGS84 latitude |
| `lon` | `FloatField(null=True, blank=True)` | WGS84 longitude |
| `city` | `CharField(max_length=100, blank=True)` | Locality name |
| `state` | `CharField(max_length=10, blank=True)` | State/province short code (e.g. CA) |
| `country` | `CharField(max_length=2, blank=True)` | ISO 3166-1 alpha-2 (e.g. US) |
| `postal_code` | `CharField(max_length=20, blank=True)` | ZIP or postal code |
| `street_address` | `CharField(max_length=200, blank=True)` | Optional; street name preferred for residential display |
| `place_id` | `CharField(max_length=300, blank=True)` | Google Places place ID |
| `geocode_source` | `CharField(max_length=20, blank=True)` | See sources below |
| `geocode_confidence` | `CharField(max_length=10, blank=True)` | `high`, `medium`, `low` |
| `geocode_at` | `DateTimeField(null=True, blank=True)` | When coordinates were set |

**`geocode_source` values:**

| Value | Meaning |
|-------|---------|
| `gps` | Phone GPS used as the pin (custom name or city-only; no Places geometry) |
| `places_lookup` | Nearby Lookup Places pick; saved lat/lon is Google place geometry |
| `map_pin` | User dropped a pin on the map picker |
| `text_search` | User searched by name and chose a Places result; Google geometry |
| `backfill_auto` | Backfill tool, no operator review |
| `backfill_confirmed` | Backfill tool, operator confirmed match |
| `manual` | Coordinates entered manually by admin |

### Indexes to add

- `(lat, lon)` - geographic queries
- `(state, city)` - filter queries
- `(country, state)` - regional filter rollup
- `(library, place_id)` - dedup lookup when place_id is present

### Why `place_id` matters

Storing the Google place ID allows:
- Deduplication: two entries for the same venue can be linked
- Refreshing data later (name or address changes)
- Future: merging Location records that represent the same real place

Phase 1: if the same library already has a Location with this
`place_id`, reuse that row (silent) rather than creating a duplicate.
Do not build a merge-confirmation UI in Phase 1; rely on existing
combine tooling for messy name duplicates.

### No changes to `Game` or `GameParticipantResult`

The game already has a FK to Location. All geographic data lives on
Location, not Game. Once a Location is geocoded, all past and future
games at that location get the coordinates for free.

### No global venue registry

Each group retains its own LocationLibrary. If two groups play at the
same physical venue, they hold separate Location rows. Cross-group
deduplication via a shared venue registry is not planned.

---

## Geocoding strategy

### When to capture coordinates

Coordinates are captured when the user sets location via Lookup, map
picker, or when backfill fills a null row. They are **not** inferred
automatically from a bare typed name with no geo payload.

### Coordinate precision

Store 6 decimal places (approximately 11cm accuracy). This is more than
sufficient for neighborhood/city queries and map display. `FloatField`
is acceptable at LeaderLodge scale.

### City-only Lookup row

Today Lookup can offer a synthetic first option that is only
"City, ST" (no venue). Phase 1 policy:

- If the user picks the city-only row: store name as that text; store
  **phone GPS** as lat/lon (`geocode_source=gps`); leave `place_id`
  blank; set city/state from the label when parseable.
- No Google place geometry for that row, so phone GPS is correct per
  the coordinate source rule.
- Do not invent a city centroid without a Places result.

---

## Phase 1 save path

Today Lookup only writes a name string into the location input. GPS and
Places fields are discarded. `nearbySearch` requests only
`displayName` and `addressComponents`. Phase 1 must close that gap.

### Client (`location_lookup.js`)

1. Request additional Places fields: `location`, `id` (place ID), and
   address components needed for city/state/country/postal.
2. On Lookup start, retain device coords only for nearby search and as a
   fallback pin (custom name / city-only). Do not send phone lat/lon as
   the saved pin when the user picks a Places result.
3. On Places pick: set hidden geo from **Google** `place.location` (and
   address / place_id); `location_geocode_source=places_lookup`.
4. On custom name after Lookup (or city-only row): set hidden geo from
   **phone** GPS; `location_geocode_source=gps`; no place_id.
5. Hidden fields (or one JSON field) alongside the visible name, e.g.:
   - `location_lat`, `location_lon` (single pair only)
   - `location_city`, `location_state`, `location_country`
   - `location_postal_code`, `location_place_id`
   - `location_geocode_source`
6. Same payload on **create** and **edit** game forms.
7. If the user never runs Lookup and only types a name, leave geo
   fields empty (null coords until reuse-of-geocoded or backfill).

### Server (`resolve_game_location` / `get_or_create_location`)

1. Accept optional geo kwargs with the location name.
2. Resolve name as today (exact / fuzzy / create).
3. Apply [fill-in and overwrite rules](#fill-in-and-overwrite-rules).
4. Create and edit game views must pass geo fields from the form into
   resolve.

### Docs

Update `docs/google-places.md`: fields requested, what is saved, and
any new API restrictions (Geocoding API when map picker needs reverse
geocode).

---

## The back-entry problem

When a game is entered hours or days after it was played, device GPS
reflects the user's current location, not the venue.

**Policy (single rule):** GPS Lookup / "Use my location" is **always
available**, regardless of `played_on`. No date-based hiding. Users are
trusted to use text search or map pin when they are not at the venue.
Optional UX later: soft hint when `played_on` is not today ("GPS is
your current position; search if you are away from the venue").

---

## Backfill tool

### Goal

For each Location with `lat IS NULL`, attempt to geocode by name.
Present candidates for review. Store the confirmed match. This is the
safety net so name-only locations still join the map.

### Server API key (CLI) vs browser key (Admin UI)

`GOOGLE_PLACES_API_KEY` is browser-restricted (HTTP referrers). A Django
management command cannot use it for Places text search.

- **Admin UI backfill (required early):** runs Places search in the
  browser with the existing browser key, shows candidates and a
  mini-map, saves the operator's pick. Primary path for reviewing large
  existing location libraries.
- **CLI backfill:** needs a separate env var, e.g.
  `GOOGLE_PLACES_SERVER_API_KEY`, IP-restricted (or used only from
  trusted operator machines). Document in `docs/google-places.md` and
  `.env.example`. Optional convenience alongside Admin UI; if absent,
  CLI auto-search is disabled but manual coord entry still works.

### Management command: `geocode_locations`

```
python manage.py geocode_locations [options]

Options:
  --dry-run          Show what would be searched, make no changes
  --limit N          Process at most N locations (default: 50)
  --group NAME       Restrict to a specific group's library
  --auto-confirm     Accept top result automatically (no review)
                     Only use when confidence is high
```

**Algorithm per location:**
1. Text-search Places for the location name + city/state hint (from the
   group's other geocoded locations when available).
2. Return up to 3 candidates with name, address, lat/lon, place_id.
3. Interactive prompt:
   `[1/2/3] pick, [s] skip, [m] enter coordinates manually, [q] quit`
4. On selection, write lat, lon, city, state, country, place_id,
   `geocode_source=backfill_confirmed`, `geocode_confidence=medium`.
5. Log skipped locations for manual follow-up.

### Admin UI backfill (required early)

Required in Phase 2, not optional. Existing datasets are large enough
that operators need a reviewable UI, not CLI alone.

Django admin (or staff Location list) action:

- Filter / select ungeocoded locations (by library / group)
- For each (or batch): Places text search via the **browser** key
- Modal with up to 3 candidates, address text, and a mini-map preview
- Operator confirms match, skips, or enters coordinates manually
- Saves with `geocode_source=backfill_confirmed`

This is the main tool for bringing historical name-only locations onto
the map before map viewer / AI geo features depend on coverage.

### Estimate

Groups may have large existing location libraries (well beyond a
handful of venues). Budget Phase 2 for operator time in the Admin UI
across libraries. Per-search API cost remains small inside the free
credit; the bottleneck is human confirmation quality, which is why the
Admin UI ships early.

---

## Map picker - game recording

### Purpose

Replaces and extends the current GPS Lookup button. Three ways to set
location:

1. **GPS Lookup** - tap to detect nearby venues (scenario A / C)
2. **Text search** - type a venue name, see Places suggestions on a map
   (scenario B)
3. **Drop pin** - pan/zoom and tap to place a pin (scenario B)

### When it appears

- Current Lookup button becomes a "Set location" button
- Opens a modal (or bottom sheet on mobile) containing the map

Coexists with the open mobile TODO that may use a native `<select>` of
group locations on small viewports: select/reuse remains for known
names; Set location remains the path for GPS / search / pin.

### Modal layout

```
+------------------------------------------+
| Set location                          [x] |
+------------------------------------------+
| [Search field]          [Use my location] |
+------------------------------------------+
|                                          |
|           Google Maps                    |
|         (full-width, ~60vh)              |
|                                          |
+------------------------------------------+
| Selected: The Parlor Room, Los Angeles   |
|           [Clear]              [Confirm] |
+------------------------------------------+
```

- Search field: Places text search (results as map pins); saved pin is
  **Google** place lat/lon
- "Use my location": GPS nearby search; if user picks a Places result,
  saved pin is still **Google** place lat/lon (phone GPS only discovers
  candidates). Always shown; see back-entry policy.
- Drop pin: reverse-geocode for address label; saved pin is **tap**
  lat/lon
- Confirm writes name + single geo payload into the form (same hidden
  fields as Phase 1) and closes the modal

### Fallback

If the user closes without confirming, the location field is unchanged.
Text entry and autocomplete still work for typed names and reuse.

---

## Map viewer - explore by location

### URL

`/games/map/` - requires authentication. Shows the user's groups'
game locations. Add a nav entry when the page ships.

### Empty state

If the group has locations but none geocoded, show a short message
pointing at Lookup / backfill rather than an empty map.

### Layout

```
+--[filters sidebar]--+--[full map]--+
| Group:  [select]    |              |
| Game:   [select]    |   pins       |
| Player: [select]    |              |
| Date:   [from][to]  |              |
| City:   [text]      |              |
| State:  [select]    |   clusters   |
|                     |              |
| [Apply] [Reset]     |              |
+---------------------+--------------+
```

On mobile, filters collapse to a drawer toggled by a filter icon.

### Pin popup (on tap/click)

```
+-------------------------------+
| The Parlor Room               |
| Los Angeles, CA               |
+-------------------------------+
| Dominos   8 games             |
| Backgammon  3 games           |
+-------------------------------+
| [View games at this location] |
+-------------------------------+
```

Tapping "View games" navigates to the game list filtered by location.

### Data endpoint

`GET /api/map/locations/` - returns GeoJSON FeatureCollection.

Query parameters mirror the filter sidebar. Server applies filters
before returning so the client never receives irrelevant pins.

Response shape:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [-118.25, 34.05] },
      "properties": {
        "location_id": 42,
        "name": "The Parlor Room",
        "city": "Los Angeles",
        "state": "CA",
        "game_counts": { "dominos": 8, "backgammon": 3 },
        "total_games": 11
      }
    }
  ]
}
```

For clustered responses, the server can return pre-aggregated cluster
centroids (see Performance section).

---

## Location filters

### Supported filter dimensions (map viewer)

| Filter | Source | Notes |
|--------|--------|-------|
| Group | `GroupMembership` | multi-select for users in multiple groups |
| Game type | `Game.game_type_code` | checkboxes using existing game type list |
| Player | `GroupPlayer` | type-ahead by name |
| Date range | `Game.played_on` | from / to date pickers |
| City | `Location.city` | free-text or dropdown of known values |
| State | `Location.state` | dropdown populated from data |
| Country | `Location.country` | dropdown; defaults to US |
| Location name | `Location.name` | free-text search |

### Granularity levels

- **Venue** - specific Location record
- **City** - all venues in a city (city + state match)
- **State** - all venues in a state
- **Country** - all venues in a country

The viewer URL encodes active filters so views can be bookmarked and
shared (within the group's privacy constraints).

---

## Leaderboard location filters

Ranking already accepts `location_id` in
`leaderlodge/leaderboards/service.py`. Ask already exposes
`query_location_leaderboard`. The **leaderboard page UI does not**
offer a location filter yet.

### Phase addition

- Leaderboard (and optionally Hall of Fame) UI: filter by venue from the
  group's location library (ids that have games for the current game
  type).
- After city/state fields are populated: optional city/state filters
  that expand to matching `location_id`s server-side.
- Reuse the same period / game-size controls already on the page.

This is separate from the map viewer filters but should use the same
Location fields and naming conventions.

---

## AI integration (Ask the Lodge)

Ask already supports venue leaders via `query_location_leaderboard`
(`location_id` or `location_query`). Geo fields unlock **regional**
questions; they are not required for "Who leads at Home?".

### Approach (matches existing tool architecture)

Do **not** invent an LLM "filter specification" that the app interprets.
Extend validated Ask tools and Python execution:

1. Enrich tool results and optional context with city/state when
   present on Location.
2. Add city/state (and later optional bbox) parameters to location-aware
   standings tools, or a small `query_locations` / region leaderboard
   helper that resolves venues then ranks.
3. Update docs and in-app examples when geo Ask capabilities ship:
   - `docs/ask-the-lodge-capabilities.md`
   - `docs/features.md`
   - In-app Ask Examples (`leaderlodge/insights/ask_examples.py` and the
     Ask Examples UI at `/insights/ask/examples/`)
4. Contextual insights (page-bound JSON): include city/state on game
   rows when available (matchup / game detail).

### Question types

| Supported when data exists | Tool direction |
|----------------------------|----------------|
| Who leads at venue X? | Existing `query_location_leaderboard` |
| Who leads in city / state? | New or extended tool args |
| Where do we play most? | Aggregate over Location with coords/city |
| West side of LA / arbitrary polygons | **Later / unsupported** until a real geo tool exists |

### Sparse data

If few locations are geocoded, regional answers are incomplete. Prompt
and/or answer footer should note when coverage is thin.

Indoor vs outdoor is **out of scope** unless an explicit field is added
later; do not infer from Places types in v1.

---

## Map provider: Google Maps JS

### Decision

Google Maps JavaScript API is the map provider for the map picker and
the map viewer.

**Reasons:**
- Already integrated: `GOOGLE_PLACES_API_KEY`, Places API (New), and
  `location_lookup.js`.
- Browser-restricted key in the page; no JWT map-token service for
  display.
- Single provider for place IDs, geocoding, and map UI.
- Free credit covers expected volume.

### APIs used

| API | Purpose | Key |
|-----|---------|-----|
| Maps JavaScript API | Map display, markers | Browser key (already) |
| Places API (New) | Nearby search, text search, place details | Browser key; server key for CLI backfill |
| Geocoding API | Reverse geocode for drop-pin (Phase 3+) | Enable on project; add to browser key API restrictions; update `docs/google-places.md` |

### Custom markers

Use `google.maps.marker.AdvancedMarkerElement` with HTML `content` for
game-type icons (see Custom pins).

---

## Custom game-type pins

### Existing assets

Game type icons (PNG) are already at `static/img/game-types/`:
- `backgammon.png`
- `dominos.png`
- `mahjongg.png`
- `pickleball.png`
- `progressiverummy.png`

### Pin design

Each pin is a small colored circle with the game icon centered inside,
built as an HTML element passed to `AdvancedMarkerElement`. When a
location has multiple game types, the dominant type (most games)
determines the pin icon; a count badge shows total distinct types.

**Pin states:**
- Default: colored circle with game icon
- Hover/selected: slightly larger, drop shadow, tooltip with location name
- Clustered: gray bubble with a count number

### Pin template

A single HTML template element cloned per pin, with the game icon
`src` swapped per game type. Keeps the DOM lightweight.

### Cluster pins

Clusters use a plain numeric badge (no game icon) since they may span
multiple game types. Color indicates approximate count range
(e.g. green=1-5, yellow=6-20, red=20+).

---

## Shared map component

Both the map picker and the map viewer use the same underlying
JavaScript module. The mode is set at initialization.

### Module interface

```javascript
// static/js/location_map.js

LeaderLodgeMap.init({
  container: HTMLElement,        // element to mount into
  mode: 'picker' | 'viewer',
  apiKey: string,                // GOOGLE_PLACES_API_KEY from template context
  onSelect: (location) => {},    // picker only
  initialRegion: { lat, lon, zoom },
  filters: { ... },             // viewer only
});

LeaderLodgeMap.setFilters({ ... });   // viewer: update displayed pins
LeaderLodgeMap.destroy();
```

The browser `apiKey` is already passed via `data-api-key` today. The
server backfill key is separate and never exposed to templates.

### Picker-specific behavior

- Search bar and "Use my location"
- On select: `onSelect({ name, lat, lon, city, state, place_id, geocode_source })`
- No filter sidebar

### Viewer-specific behavior

- Loads pins from `/api/map/locations/` with current filters
- Cluster annotations; click cluster to zoom; click pin for popup
- Re-fetches when the map region changes significantly (viewport loading)

---

## Performance and clustering

### Problem

A group with 500+ games at 20 locations is trivial. Larger pin counts
need clustering.

### Client-side clustering

Use **Supercluster** in the browser. This repo has no `package.json` /
JS bundler: **load from CDN or vendor a minified file under
`static/js/`**. Do not assume `npm install`.

Google Maps zoom-change events trigger re-clustering.

### Server-side pre-aggregation (later)

If pin counts grow large (1,000+ distinct locations), `/api/map/locations/`
can accept `zoom` and return pre-aggregated centroids. Implement only
when client-side clustering is noticeably slow (~500+ visible pins).

### Viewport loading

Fetch pins for the visible bounding box plus a margin.

Endpoint parameter: `?bbox=lon_min,lat_min,lon_max,lat_max`

---

## Privacy model

### Current model

Locations are per-group. Members see their groups' locations.
Anonymous users do not see non-demo location data.

### Proposed extensions

| Scenario | Visibility |
|----------|-----------|
| Group member views map | Sees all geocoded locations for their groups |
| Non-member views a group | No location data (same as today) |
| Demo group | Locations and coordinates visible to anonymous visitors; demo data already obfuscates personal homes |
| Admin/staff | Sees all locations across all groups |

### Home addresses (v1)

v1 stores precise coordinates for homes when GPS or pin is used.
Security hardening (fuzzing pins, hiding street numbers) is optional
later; product priority is complete lat/lon coverage.

When display stripping is added: prefer street name only in
`street_address` / popup text; pin may still use stored coordinates.

---

## Existing location tooling

- `rename_location` / `combine_locations` in `leaderlodge/groups/locations.py`
  and group location UI already exist.
- On **combine**: keeper keeps its geo fields; if keeper has null coords
  and source has coords, copy source geo onto keeper before delete.
- Open TODO "Merge similar locations tool" should respect the same rule
  once geo fields exist.
- Phase 1 place_id reuse is silent; name-merge UX stays on existing
  combine flows.

---

## Out of scope

- Cross-group shared venue registry
- Indoor vs outdoor classification
- Arbitrary polygon / "west side" geo queries (until a dedicated tool)
- Native iOS/Android map apps
- Overwriting coords on every reuse of a geocoded Location

---

## Documentation and examples checklist

When a phase ships user-visible behavior, update the matching docs (and
examples) in the same phase, not as a follow-up:

| When | Update |
|------|--------|
| Phase 1 | `docs/google-places.md` (fields saved, Places field list) |
| Phase 2 | `docs/google-places.md` (server key if CLI; Admin backfill notes) |
| Phase 3+ | `docs/features.md` (Set location / map picker) |
| Phase 4+ | `docs/features.md` (map viewer, leaderboard venue filter) |
| Phase 6 | `docs/features.md`, `docs/ask-the-lodge-capabilities.md`, in-app Ask Examples (`ask_examples.py` + Examples UI) |

`docs/location-map.md` remains the planning source of truth until
features are marked shipped in `features.md`.

---

## Implementation phases

**Deployment priority:** Phase 1 ships to production as soon as it is
complete, before any map UI exists. Accumulate real coordinate data via
Lookup. Phase 2 Admin UI backfill runs early against large existing
datasets so map and AI geo features have coverage. Later map UI depends
on that data.

### Phase 1 - Schema and data foundation

**Status: done (this phase).**

**Done when:** new and edited games can persist lat/lon (and address
fields) from Lookup; reuse of a geocoded Location does not overwrite
coords; name-only entry still works with null coords.

- [x] Add coordinate and address fields to `Location` (+ indexes)
- [x] Migration (nullable fields; no backfill in migration)
- [x] Client: Places fields + hidden geo payload; Places pick saves Google
  lat/lon; custom/city-only after Lookup saves phone GPS
- [x] Server: resolve/create with fill-in and overwrite rules
- [x] Create and edit game forms
- [x] Update `docs/google-places.md`
- [x] Carry Lookup geo through setup to roster save step

### Phase 2 - Backfill tool (CLI + Admin UI)

**Done when:** staff can geocode large existing `lat IS NULL` libraries
via Admin UI (candidates + mini-map); CLI works when a server key is
configured; seed/demo and production libraries can be brought to useful
coverage before map viewer work.

- Admin UI backfill action (required): list ungeocoded locations,
  Places search in browser, candidate modal with mini-map, confirm /
  skip / manual coords
- `geocode_locations` management command (interactive; needs
  `GOOGLE_PLACES_SERVER_API_KEY`)
- Document keys and operator workflow in `docs/google-places.md`
- Backfill existing production / seed / demo locations as needed for
  map and Ask coverage

### Phase 3 - Map picker

**Done when:** user can set location via GPS, text search, or drop pin;
geo payload matches Phase 1 hidden fields (scenario B).

- "Set location" modal on game recording form
- Modes: GPS lookup, text search, drop pin
- Enable Geocoding API on the browser key if reverse geocode is used
- Base `location_map.js` module
- Update `docs/features.md`

### Phase 4 - Map viewer + leaderboard venue filter

**Done when:** authenticated users can open `/games/map/` with filters;
leaderboard UI can filter by venue.

- `/games/map/` view, nav entry, empty state
- `/api/map/locations/` GeoJSON endpoint with filters
- Filter sidebar; viewport loading; Supercluster via CDN/vendor
- Pin popup linking to filtered game list
- Leaderboard UI location (venue) filter wired to existing service
- Update `docs/features.md`

### Phase 5 - Custom pins

- HTML pin template per game type using `AdvancedMarkerElement`
- Cluster badge annotation; selected/hover states

### Phase 6 - AI / Ask geo extensions

**Done when:** Ask can answer city/state venue questions when data
exists; docs and **in-app** examples updated; sparse-data caveat
documented.

- Extend Ask tools for city/state (and document limits)
- Enrich contextual insight JSON with city/state when present
- Update `docs/ask-the-lodge-capabilities.md`
- Update `docs/features.md` (location-aware Ask)
- Update in-app Ask Examples: `leaderlodge/insights/ask_examples.py`
  and the Examples UI (`/insights/ask/examples/`) with venue and
  city/state questions that match supported tools

### Phase 7 - Performance hardening

- Server-side clustering if needed
- Caching GeoJSON responses (invalidate on new game / location geocode)
- Load testing with realistic pin counts
