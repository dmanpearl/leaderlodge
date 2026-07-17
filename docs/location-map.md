# LeaderLodge Location Map

Plan for displaying game-play locations as pins on a map, with rich
filtering, a map-based location picker for game recording, and AI-aware
geographic queries.

**Status: Phase 1 done. Phase 2a (Set place map picker) implemented.
Phase 2b (merge duplicates) and later phases still planning.**

---

## Progress (follow along here)

Search this file for `>>> NEXT UP <<<` to jump to the active phase.

| Phase | Name | Status |
|-------|------|--------|
| 1 | Schema and data foundation | **done** |
| 2 | Set place (map picker + search + assign) + merge | **2a done; 2b >>> NEXT UP <<<** |
| 3 | Map picker on Record Game | not started |
| 4 | Map viewer + leaderboard venue filter | not started |
| 5 | Custom pins | not started |
| 6 | AI / Ask geo extensions | not started |
| 7 | Performance hardening | not started |

**How to use this doc while we build:**

1. Open **Progress** (this section) or Cmd/Ctrl+F `>>> NEXT UP <<<`.
2. Jump to **Implementation phases** for the checklist of the active
   phase (`### Phase N - ...`).
3. For design detail of that phase, use the matching topic section
   (examples below). Update the Progress table and move
   `>>> NEXT UP <<<` when a phase finishes.

| When working on | Read these sections |
|-----------------|---------------------|
| Phase 2 | Set place map picker; Location library tools; Shared map component |
| Phase 3 | Map picker on Record Game; Phase 1 save path |
| Phase 4 | Map viewer; Location filters; Leaderboard location filters |
| Phase 5 | Custom game-type pins |
| Phase 6 | AI integration; Documentation checklist |
| Phase 7 | Performance and clustering |

Capture rules (always in force): **Capture scenarios (product intent)**.

---

## Table of contents

1. [Progress (follow along here)](#progress-follow-along-here)
2. [Overview](#overview)
3. [Capture scenarios (product intent)](#capture-scenarios-product-intent)
4. [Database schema changes](#database-schema-changes)
5. [Geocoding strategy](#geocoding-strategy)
6. [Phase 1 save path](#phase-1-save-path)
7. [The back-entry problem](#the-back-entry-problem)
8. [Location library tools](#location-library-tools)
9. [Set place map picker (shared)](#set-place-map-picker-shared)
10. [Map picker on Record Game](#map-picker-on-record-game)
11. [Map viewer - explore by location](#map-viewer---explore-by-location)
12. [Location filters](#location-filters)
13. [Leaderboard location filters](#leaderboard-location-filters)
14. [AI integration (Ask the Lodge)](#ai-integration-ask-the-lodge)
15. [Map provider: Google Maps JS](#map-provider-google-maps-js)
16. [Custom game-type pins](#custom-game-type-pins)
17. [Shared map component](#shared-map-component)
18. [Performance and clustering](#performance-and-clustering)
19. [Privacy model](#privacy-model)
20. [Existing location tooling](#existing-location-tooling)
21. [Out of scope](#out-of-scope)
22. [Documentation and examples checklist](#documentation-and-examples-checklist)
23. [Implementation phases](#implementation-phases)

---

## Overview

The Location model already exists and is per-group (each group has its
own LocationLibrary). A Location has only a name today. The plan is to:

- Add coordinate and structured address fields to Location
- Capture one lat/lon per Location at recording time (Places geometry,
  map pin, or device GPS when there is no place point)
- Reuse saved coordinates when the user picks an existing Location
- Provide in-app **Set place** tools (map picker + editable Places search)
  to geocode informal Location rows in one edit, plus find/merge duplicates
- Build a map viewer with pin clustering and rich filters
- Add location filters on the leaderboard UI (service already supports
  venue filter; Ask already has `query_location_leaderboard`)
- Build an enhanced map-based picker on Record Game (Phase 3; same module
  as Set place)
- Share a single map component between the picker and the viewer

**Guiding rule:** every Location stores one lat/lon and should end up
with the best point we can obtain. Places picks use Google geometry
(not phone GPS). Prefer capture at entry; use explicit re-geocode on the
Locations page for historical rows; never require a fresh lookup when
reusing a Location that already has coordinates.

---

## Capture scenarios (product intent)

These are the recording behaviors the plan must support.

### Coordinate source rule (single lat/lon)

Each Location stores **exactly one** `lat`/`lon` pair. No separate phone
vs Google coordinate fields.

| User action | Saved lat/lon | `geocode_source` |
|-------------|---------------|------------------|
| Picks a Places result (Near me or in-field Search) | **Google** place geometry (overrides phone GPS) | `places_lookup` or `text_search` |
| Drops a map pin | Pin coordinates | `map_pin` |
| Types a custom name after Near me (e.g. "Sally's House") with GPS available | **Phone** GPS | `gps` |
| City-only Near me row ("Los Angeles, CA") | **Phone** GPS | `gps` |
| Types a name with no Near me / Search / picker geo | None (`lat` null) until explicit re-geocode or fill-in on save | (blank) |
| Reuses an existing Location that already has coords | Existing saved lat/lon (no new lookup) | unchanged |

Phone GPS is used only to **discover** nearby places and as the pin when
there is no Google place point. A Places pick always prefers Google
lat/lon over the device reading.

Privacy of precise home coordinates is not a blocker for v1; store full
precision. Optional street-number stripping for display remains a later
nice-to-have (see Privacy).

### A. Record at the play location (typical)

User is physically at the venue and taps **Near me** (or later, "Use my
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

**Near me** remains available (see Back-entry policy) so users who are
actually still near the venue can use it; users who are elsewhere should
prefer search or map pin. If they do use Near me and pick a Places
result, Google place lat/lon is still what is saved (same as A).

### C. Custom name while Near me GPS is available

User runs Near me (or has GPS), ignores the place list, and types
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
| Existing Location, explicit re-geocode from Locations page | Set or replace coords (user confirms if coords already set) |
| Typed name only, no geo payload | Create/reuse name only; leave lat/lon null until explicit re-geocode or fill-in on a later save |

Goal: **management system** so ungeocoded rows are visible on the
Locations page and fixable in one edit; reuse never burns API calls or
relocates a known venue without user intent.

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
| `places_lookup` | Near me Places pick; saved lat/lon is Google place geometry |
| `map_pin` | User dropped a pin on the map picker |
| `text_search` | User searched by name and chose a Places result; Google geometry |
| `manual` | Coordinates entered manually by admin |

Set place on the Locations page uses the same sources as recording
(`places_lookup`, `gps`, `map_pin`, `text_search`) depending on how the
user picks the pin.

`backfill_auto` and `backfill_confirmed` are reserved in the schema but
**not used**. Bulk name-based backfill (CLI or Admin) is out of scope;
vague venue names do not geocode reliably without a human who knows the
place.

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

Coordinates are captured when the user sets location via Near me / Search, map
picker, explicit re-geocode on the Locations page, or when a save
includes a geo payload that fills a null row. They are **not** inferred
automatically from a bare typed name with no geo payload.

### Coordinate precision

Store 6 decimal places (approximately 11cm accuracy). This is more than
sufficient for neighborhood/city queries and map display. `FloatField`
is acceptable at LeaderLodge scale.

### City-only Near me row

Today Near me can offer a synthetic first option that is only
"City, ST" (no venue). Phase 1 policy:

- If the user picks the city-only row: store name as that text; store
  **phone GPS** as lat/lon (`geocode_source=gps`); leave `place_id`
  blank; set city/state from the label when parseable.
- No Google place geometry for that row, so phone GPS is correct per
  the coordinate source rule.
- Do not invent a city centroid without a Places result.

---

## Phase 1 save path

Today Near me only writes a name string into the location input. GPS and
Places fields are discarded. `nearbySearch` requests only
`displayName` and `addressComponents`. Phase 1 must close that gap.

### Client (`location_lookup.js`)

1. Request additional Places fields: `location`, `id` (place ID), and
   address components needed for city/state/country/postal.
2. On Near me start, retain device coords only for nearby search and as a
   fallback pin (custom name / city-only). Do not send phone lat/lon as
   the saved pin when the user picks a Places result.
3. On Places pick: set hidden geo from **Google** `place.location` (and
   address / place_id); `location_geocode_source=places_lookup`.
4. On custom name after Near me (or city-only row): set hidden geo from
   **phone** GPS; `location_geocode_source=gps`; no place_id.
5. Hidden fields (or one JSON field) alongside the visible name, e.g.:
   - `location_lat`, `location_lon` (single pair only)
   - `location_city`, `location_state`, `location_country`
   - `location_postal_code`, `location_place_id`
   - `location_geocode_source`
6. Same payload on **create** and **edit** game forms.
7. If the user never runs Near me / Search and only types a name, leave geo
   fields empty (null coords until explicit re-geocode or fill-in).

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

**Policy (single rule):** Near me / "Use my location" is **always
available**, regardless of `played_on`. No date-based hiding. Users are
trusted to use text search or map pin when they are not at the venue.
Optional UX later: soft hint when `played_on` is not today ("GPS is
your current position; search if you are away from the venue").

---

## Location library tools

### Why not fully automated bulk backfill?

Most historical locations are informal names ("Sally's House",
"Home - Island", vague restaurant labels, sometimes with a state code).
Automated Places text search on those names returns multiple low-confidence
matches. A hands-off management command or staff batch backfill would spend
API calls and still produce wrong pins.

**Decision:** no unattended auto-assign. Coverage for existing rows comes from
**human-in-the-loop** tools: in-app **Set place**, and the optional interactive
CLI `backfill_location_places` (accept/reject/skip each Places result; see
`docs/google-places.md`).

### A. Set place (explicit re-geocode)

**Goal:** edit the **Location** row (not one Game), so one action updates
every game that uses that venue.

**Requires map picker from day one.** Nearby-only Near me (device GPS) is
not enough: the user is often at home editing a game played elsewhere.
They must pan the map, drop a pin, search by business name, and pick a
Google place.

#### Canonical workflow (map + pin lookup)

Example: informal name `Cafe 50s`; real venue `Café 50's, West Los Angeles, CA`.

1. View Game detail
2. Edit game
3. Location: open **Set place** (updates the shared Location, not only
   this game's text field)
4. Map opens (default region: group centroid, last geocoded venue in
   area, or US overview; not device GPS as the pin)
5. Pan/zoom to West LA; drop pin on the restaurant
6. **Pin lookup:** nearby Places at the pin; list results on map
7. Select Google place (`Café 50's, ...`)
8. **Assign**
9. Location `Cafe 50s` now has lat/lon, `place_id`, city, state; all
   games at that Location share the pin

Name policy on Assign: keep informal `Cafe 50s` by default; optional
checkbox "Use place name" to adopt the Google display name.

#### Canonical workflow (editable text search)

Example: `Pancake House, OR` (informal); user knows the business name.

1. Same entry (Edit game, Locations list, etc.)
2. Search field pre-filled from current Location name; **user may edit**
   query (e.g. `Pancake House Oregon` or full address)
3. Places text search; results as map pins
4. Select suggestion
5. **Assign**

Saved lat/lon is always **Google place geometry** for a Places pick.

#### Entry points (Phase 2)

| Entry | Notes |
|-------|-------|
| **Edit game** Location | Primary; user story above |
| **Group Locations** row action Set place | Same modal |
| Game detail | Link: "Set place for all games here" when `game.location` set |

**Who can use it:** same permission as rename/combine on Locations
(group editors / owners).

**Overwrite rules:**

| Current state | On Assign |
|---------------|-----------|
| `lat IS NULL` | Write geo from pick |
| Already geocoded | Confirm: "Replace pin for all N games?" |

`geocode_source`: `text_search` (search pick), `map_pin` (pin only, no
place match), or `places_lookup` (pin lookup nearby pick). Not device
`gps` for this flow unless user explicitly uses "Use my location".

**Why this beats bulk backfill:** user at home can still fix `Cafe 50s`
by map + search; no blind auto-geocode on the informal string.

### B. Find and merge duplicate locations

**Goal:** reduce duplicate Location rows ("Home" vs "Home - Island",
typos, rename drift) so geo and game counts consolidate.

**Builds on:** existing `combine_locations` and rename on the Locations
page; open TODO "Merge similar locations tool".

**UI concept:**

- **Group Locations:** "Find duplicates" (or badge when suggestions exist)
- Server suggests candidate pairs using existing fuzzy match scoring
  (`score_location_match`, library-scoped), plus optional same
  `place_id` when both geocoded
- List shows: name A, name B, game counts, whether either has lat/lon
- User picks keeper, confirms merge (reuse existing combine confirmation)
- On merge: keeper keeps geo; if keeper null and source has coords, copy
  (existing `copy_geo_from_source_if_needed` rule)

**Not in scope for v1 of this tool:** cross-group merge, auto-merge
without confirmation, merging more than two at once.

### Locations list enhancements (Phase 2)

Support the tools above on `templates/groups/location_list.html`:

- Column or badge: geocoded vs not (`lat` null)
- Sort/filter: ungeocoded first (optional default for editors)
- Row actions: Rename, Combine (existing), **Set place**, Delete (existing)

### Estimate

Per-group libraries are large in count but human-driven. Budget Phase 2
for UX on the Locations page, not operator CLI sessions. Places API cost
stays low because users only search when they choose to set a place.

---

## Set place map picker (shared)

Built in **Phase 2** for Location assign; reused in **Phase 3** on Record
Game. One module: `static/js/location_map.js`.

### Modes

| Mode | Purpose | On confirm |
|------|---------|------------|
| `assign` | Set place on existing Location | POST geo to Location; updates all games |
| `record` | Record Game (Phase 3) | Write geo hidden fields + name on game form |

### Modal layout

```
+------------------------------------------+
| Set place for Cafe 50s (12 games)     [x] |
+------------------------------------------+
| [Search: Cafe 50s____________]  [Search] |
| [Pin lookup]              [Use my location] |
+------------------------------------------+
|                                          |
|           Google Maps                    |
|    (draggable pin + result markers)      |
|                                          |
+------------------------------------------+
| Selected: Café 50's, West Los Angeles    |
| [ ] Use place name                       |
|           [Clear]              [Assign]   |
+------------------------------------------+
```

### Behaviors

1. **Editable search:** input pre-filled from Location name; user edits
   before search (`Pancake House, OR` to `Pancake House Oregon`).
2. **Text search:** Places API; markers on map; select one.
3. **Drop pin:** tap map to place crosshair/pin; does not save until Assign.
4. **Pin lookup:** nearby Places at pin (same types as Near me); user
   picks a business. Primary path when user knows where on map but not
   the exact query string.
5. **Use my location:** optional; centers map and runs nearby search.
   Not the default for assign mode (user often away from venue).
6. **Assign:** writes geo via `apply_location_geo(..., force=...)`;
   optional adopt place name.

### APIs

Enable **Geocoding API** on the browser key if reverse-geocode is used
for pin-only assigns. Places API (New) for search and pin lookup.

### Server

`POST` assign endpoint (e.g. group location set-place): `location_id`,
geo payload, optional `adopt_place_name`, `confirm_replace` when coords
exist.

---

## Map picker on Record Game

**Phase 3.** Replaces the Record Game Near me / Search controls with the same modal
in `record` mode (hidden fields + location name). Phase 1 Near me remains
until Phase 3 ships.

Coexists with mobile native location `<select>` TODO: reuse for known
names; Set place for GPS / search / pin.

### Recording-specific behavior

- "Use my location" more prominent (often at venue)
- Confirm writes name + geo into game form (Phase 1 hidden fields)
- Does not require `location_id` until form save

### Fallback

Close without Assign: game form unchanged. Text autocomplete still works.

---

## Map viewer - explore by location

### URL

`/games/map/` - requires authentication. Shows the user's groups'
game locations. Add a nav entry when the page ships.

### Empty state

If the group has locations but none geocoded, show a short message
pointing at Near me / Search and **Set place** on the Locations page rather than an
empty map.

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
| Places API (New) | Nearby search, text search, place details | Browser key |
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

Both Set place (assign/record) and the map viewer use the same underlying
JavaScript module.

### Module interface

```javascript
// static/js/location_map.js

LeaderLodgeMap.init({
  container: HTMLElement,
  mode: 'assign' | 'record' | 'viewer',
  apiKey: string,
  locationId: number | null,     // assign mode
  locationName: string,          // assign: show title + pre-fill search
  gameCount: number | null,      // assign: "N games"
  onAssign: (result) => {},      // assign mode
  onSelect: (location) => {},    // record mode
  initialRegion: { lat, lon, zoom },
  filters: { ... },              // viewer only
});

LeaderLodgeMap.destroy();
```

### Assign-specific behavior

- Search pre-filled from `locationName`; user edits before search
- Pin lookup at dropped pin
- Assign POST; optional adopt place name
- Default map region not device GPS

### Record-specific behavior

- Same search / pin / pin lookup
- Confirm fills Phase 1 hidden geo fields on game form

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
  and group **Locations** page (`templates/groups/location_list.html`)
  already exist.
- On **combine**: keeper keeps its geo fields; if keeper has null coords
  and source has coords, copy source geo onto keeper before delete.
- **Phase 2** adds **Set place** (explicit re-geocode) and **Find
  duplicates** (suggested merges) on the same Locations page.
- Phase 1 place_id reuse is silent; pairwise combine stays the merge UX
  for confirmed duplicates.

---

## Out of scope

- Cross-group shared venue registry
- Indoor vs outdoor classification
- Arbitrary polygon / "west side" geo queries (until a dedicated tool)
- Native iOS/Android map apps
- Overwriting coords on every reuse of a geocoded Location during game save
- **Unattended bulk backfill:** auto-assign from name alone with no human
  confirm, Admin batch Places search, treating browser keys as server keys
- Interactive confirmed CLI (`backfill_location_places`) is allowed; see
  `docs/google-places.md`

---

## Documentation and examples checklist

When a phase ships user-visible behavior, update the matching docs (and
examples) in the same phase, not as a follow-up:

| When | Update |
|------|--------|
| Phase 1 | `docs/google-places.md` (fields saved, Places field list) |
| Phase 2 | `docs/features.md`, `docs/google-places.md` (map, search, pin lookup) |
| Phase 3+ | `docs/features.md` (Set location / map picker on Record Game) |
| Phase 4+ | `docs/features.md` (map viewer, leaderboard venue filter) |
| Phase 6 | `docs/features.md`, `docs/ask-the-lodge-capabilities.md`, in-app Ask Examples (`ask_examples.py` + Examples UI) |

`docs/location-map.md` remains the planning source of truth until
features are marked shipped in `features.md`.

---

## Implementation phases

**Deployment priority:** Phase 1 done. Phase 2 ships the shared map picker
and Set place (assign) so informal locations can be fixed from Edit Game
and Locations. Phase 3 wires the same picker to Record Game. Phase 4+
map viewer depends on geocoded data.

### Phase 1 - Schema and data foundation

**Status: done (this phase).**

**Done when:** new and edited games can persist lat/lon (and address
fields) from Near me / Search; reuse of a geocoded Location does not overwrite
coords; name-only entry still works with null coords.

- [x] Add coordinate and address fields to `Location` (+ indexes)
- [x] Migration (nullable fields; no data backfill in migration)
- [x] Client: Places fields + hidden geo payload; Places pick saves Google
  lat/lon; custom/city-only after Near me saves phone GPS
- [x] Server: resolve/create with fill-in and overwrite rules
- [x] Create and edit game forms
- [x] Update `docs/google-places.md`
- [x] Carry Near me / Search geo through setup to roster save step

### Phase 2 - Set place (map picker + assign) + merge duplicates

**Status: 2a done. 2b >>> NEXT UP <<<.**

**Done when:** from Edit Game or Locations, user can open a map, search
(editable query), drop pin, pin-lookup, pick a Google place, and Assign
to update the Location row for all linked games; duplicate merge tool
ships.

**2a - Shared map picker + Set place assign**

- [x] `location_map.js`: assign mode (map, editable search, drop pin,
  pin lookup, place select, Assign)
- [x] Enable Geocoding API on browser key if needed
- [x] Server: set-place POST on Location (`force` when replacing coords)
- [x] Edit game: Set place on Location (primary entry)
- [x] Locations list: geocoded badge; row action Set place (same modal)
- [x] Game detail link when location set
- [x] Update `docs/google-places.md` (map + search APIs)
- [x] Update `docs/features.md`

**2b - Find and merge duplicates**

- [ ] Suggest duplicate pairs (fuzzy score + optional `place_id` match)
- [ ] UI: review list, pick keeper, confirm (reuse combine flow)
- [ ] Respect geo copy rules on merge
- [ ] Update `docs/features.md`; close TODO "Merge similar locations tool"

**Not in Phase 2:** CLI batch backfill, Record Game button swap (Phase 3)

### Phase 3 - Map picker on Record Game

**Status: not started.**

**Done when:** Record Game uses the same `location_map.js` in `record`
mode; Near me / Search become Set location.

- [ ] Wire modal to game form (Phase 1 hidden geo fields)
- [ ] Keep Phase 1 Near me / Search as fallback until verified, then remove or merge
- [ ] Update `docs/features.md`

### Phase 4 - Map viewer + leaderboard venue filter

**Status: not started.**

**Done when:** authenticated users can open `/games/map/` with filters;
leaderboard UI can filter by venue.

- [ ] `/games/map/` view, nav entry, empty state
- [ ] `/api/map/locations/` GeoJSON endpoint with filters
- [ ] Filter sidebar; viewport loading; Supercluster via CDN/vendor
- [ ] Pin popup linking to filtered game list
- [ ] Leaderboard UI location (venue) filter wired to existing service
- [ ] Update `docs/features.md`

### Phase 5 - Custom pins

**Status: not started.**

- [ ] HTML pin template per game type using `AdvancedMarkerElement`
- [ ] Cluster badge annotation; selected/hover states

### Phase 6 - AI / Ask geo extensions

**Status: not started.**

**Done when:** Ask can answer city/state venue questions when data
exists; docs and **in-app** examples updated; sparse-data caveat
documented.

- [ ] Extend Ask tools for city/state (and document limits)
- [ ] Enrich contextual insight JSON with city/state when present
- [ ] Update `docs/ask-the-lodge-capabilities.md`
- [ ] Update `docs/features.md` (location-aware Ask)
- [ ] Update in-app Ask Examples: `leaderlodge/insights/ask_examples.py`
  and the Examples UI (`/insights/ask/examples/`) with venue and
  city/state questions that match supported tools

### Phase 7 - Performance hardening

**Status: not started.**

- [ ] Server-side clustering if needed
- [ ] Caching GeoJSON responses (invalidate on new game / location geocode)
- [ ] Load testing with realistic pin counts
