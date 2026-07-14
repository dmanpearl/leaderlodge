# LeaderLodge Location Map

Plan for displaying game-play locations as pins on a map, with rich
filtering, a map-based location picker for game recording, and AI-aware
geographic queries.

**Status: planning. Nothing here is implemented.**

---

## Table of contents

1. [Overview](#overview)
2. [Database schema changes](#database-schema-changes)
3. [Geocoding strategy](#geocoding-strategy)
4. [The back-entry problem](#the-back-entry-problem)
5. [Backfill tool](#backfill-tool)
6. [Map picker - game recording](#map-picker---game-recording)
7. [Map viewer - explore by location](#map-viewer---explore-by-location)
8. [Location filters](#location-filters)
9. [AI integration](#ai-integration)
10. [Map provider: Google Maps JS](#map-provider-google-maps-js)
11. [Custom game-type pins](#custom-game-type-pins)
12. [Shared map component](#shared-map-component)
13. [Performance and clustering](#performance-and-clustering)
14. [Privacy model](#privacy-model)
15. [Implementation phases](#implementation-phases)

---

## Overview

The Location model already exists and is per-group (each group has its
own LocationLibrary). A Location has only a name today. The plan is to:

- Add coordinate and structured address fields to Location
- Capture coordinates at recording time (GPS or name lookup)
- Provide a backfill tool for existing locations
- Build a map viewer with pin clustering and rich filters
- Build an enhanced map-based picker that replaces/extends the current
  Lookup button flow
- Share a single map component between the picker and the viewer

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
| `street_address` | `CharField(max_length=200, blank=True)` | Street name only for residential; omit street number and unit |
| `place_id` | `CharField(max_length=300, blank=True)` | Google Places place ID |
| `geocode_source` | `CharField(max_length=20, blank=True)` | See sources below |
| `geocode_confidence` | `CharField(max_length=10, blank=True)` | `high`, `medium`, `low` |
| `geocode_at` | `DateTimeField(null=True, blank=True)` | When coordinates were set |

**`geocode_source` values:**

| Value | Meaning |
|-------|---------|
| `gps` | GPS at time of game entry, confirmed by user |
| `places_lookup` | Chose from Places API dropdown during entry |
| `map_pin` | User dragged a pin on the map picker |
| `text_search` | User searched by name on the map picker |
| `backfill_auto` | Backfill tool, no operator review |
| `backfill_confirmed` | Backfill tool, operator confirmed match |
| `manual` | Coordinates entered manually by admin |

### Indexes to add

- `(lat, lon)` - geographic queries
- `(state, city)` - filter queries
- `(country, state)` - regional filter rollup

### Why `place_id` matters

Storing the Google place ID allows:
- Deduplication: two entries for the same venue can be linked
- Refreshing data later (name or address changes)
- Future: merging Location records that represent the same real place

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

Coordinates should be captured at the time the user sets the location,
not automatically on every game save. Two paths:

1. **GPS lookup (current Lookup button)**: user taps Lookup, picks a
   nearby place from the dropdown. The place carries coordinates and
   address components. Store them on the Location row at that moment.

2. **Map picker (planned)**: user searches or drops a pin on a map.
   Same result: coordinates stored on Location.

If the user types a location name and does not use either tool, no
coordinates are stored. The location will need backfilling later.

### Coordinate precision

Store 6 decimal places (approximately 11cm accuracy). This is more than
sufficient for "which neighborhood/city" queries and for map display.
`FloatField` gives 15 significant digits, which is more than enough.

### Deduplication on entry

When the user picks a place from the GPS lookup or map picker, check
whether another Location in the same library already has the same
`place_id`. If so, offer to merge or reuse rather than create a
duplicate entry.

---

## The back-entry problem

When a game is entered hours or days after it was played, GPS
coordinates reflect the user's current location, not the venue. The
`Game.played_on` date can be compared to the current date to detect
this.

**Policy:** GPS lookup is always available regardless of `played_on`.
No date-based restrictions are applied. Users are trusted to recognize
when GPS is unreliable for a back-entered game and to use text search
or the map picker instead.

---

## Backfill tool

### Goal

For each Location with `lat IS NULL`, attempt to geocode by name using
the Places text search API. Present candidates to an operator for
review. Store the confirmed match.

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
1. Text-search the Google Places API for the location name + city/state
   hint (derived from the group's other geocoded locations if available).
2. Return up to 3 candidates with name, address, lat/lon, place_id.
3. In interactive mode, print candidates and prompt operator:
   `[1/2/3] pick, [s] skip, [m] enter coordinates manually, [q] quit`
4. On selection, write lat, lon, city, state, country, place_id,
   `geocode_source=backfill_confirmed`, `geocode_confidence=medium`.
5. Log skipped locations for manual follow-up.

### Admin UI backfill (future)

A Django admin action on the Location list view:
- Select one or more ungeocoded locations
- Run the text search and show a modal with candidates and a mini-map
- Admin clicks the correct match; coordinates are saved
- Useful for low-volume manual cleanup without the CLI

### Estimate

Current data: 5 game types, approximately 10-30 distinct locations per
group. All locations will be processed in a single CLI session; order
does not matter. API cost for 30 text searches is negligible (well
within free tier).

---

## Map picker - game recording

### Purpose

Replaces and extends the current GPS Lookup button. Gives the user
three ways to set the game location:

1. **GPS Lookup** (current) - tap to detect nearby venues
2. **Text search** - type a venue name, see Places suggestions on a map
3. **Drop pin** - pan/zoom the map and tap to place a pin anywhere

### When it appears

The map picker is triggered from the game recording setup form:
- Current Lookup button becomes a "Set location" button
- Opens a modal (or bottom sheet on mobile) containing the map

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

- Search field uses Places text search (type-ahead, results as map pins)
- "Use my location" runs GPS lookup (hidden if `played_on < today`)
- Tapping a result pin selects it and shows name + address at bottom
- Dragging the map shows a crosshair; tapping confirms a custom pin
  (reverse-geocoded to get address)
- Confirm writes the selected name (and coordinates) to the hidden
  location field and closes the modal

### Fallback

If the user closes the modal without confirming, the location field
is unchanged. The existing text entry and autocomplete still work as
before for users who prefer typing.

---

## Map viewer - explore by location

### URL

`/games/map/` - requires authentication. Shows the user's groups'
game locations.

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

### Supported filter dimensions

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

Filters can be applied at three geographic granularities:
- **Venue** - specific Location record
- **City** - all venues in a city (city + state match)
- **State** - all venues in a state
- **Country** - all venues in a country

The viewer URL encodes active filters so views can be bookmarked and
shared (within the group's privacy constraints).

---

## AI integration

### New question types

With location data, the AI can answer geographic questions:

- "Who plays best at home games?"
- "How does my Dominos record compare indoors vs outdoors?"
- "Who has the best record on the west side of LA?"
- "Where do we play most often?"
- "Does player X perform better at their own home?"

### Implementation approach

When building the AI context for a query, include location fields in
the game history rows if they are populated:

```
Game 42 | 2025-03-15 | Dominos | The Parlor Room, Los Angeles, CA
```

The AI prompt gains a note describing available location fields so the
model knows it can filter or group by city, state, or venue name.

For spatial queries ("west side of LA"), the AI would return a filter
specification (city list, bounding box, or venue list) that the
application applies to the game data before summarizing.

**Dependency:** Location fields must be populated for AI location
queries to be meaningful. Sparse geocoding data will produce incomplete
or misleading answers. Document this limitation in the AI answer footer.

---

## Map provider: Google Maps JS

### Decision

Google Maps JavaScript API is the map provider for all map features:
the map picker and the map viewer.

**Reasons:**
- Already integrated - the `GOOGLE_PLACES_API_KEY` is set up, Places
  API (New) is enabled, and `location_lookup.js` uses it today.
  Adding a map is one more feature on the same key with zero new
  account setup.
- No token infrastructure needed - Google Maps JS uses the browser-
  restricted API key directly in the page. No server-side JWT endpoint,
  no key rotation, no PyJWT dependency.
- Familiar on all platforms - Android users see the native Google Maps
  style; iOS and desktop users know it equally well.
- Free at LeaderLodge's scale - the $200/month Google credit covers
  map loads, Places searches, and geocoding calls with large headroom.
  No additional per-year account fee.
- Single provider - all place IDs, geocoding results, and map
  interactions come from Google, eliminating any provider mismatch.

### APIs used

| API | Purpose |
|-----|---------|
| Maps JavaScript API | Map display, markers, overlays (already enabled) |
| Places API (New) | Nearby search, text search, place details (already enabled) |
| Geocoding API | Reverse geocode for drop-pin placement |

All three are enabled on the existing key and covered by the same
$200/month credit.

### Custom markers

Google Maps JS supports custom markers via `google.maps.marker.AdvancedMarkerElement`
(the modern replacement for the deprecated `Marker` class). Custom
HTML content is passed as the `content` property, allowing the same
game-type icon approach described in the Custom pins section.

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

The `apiKey` value is already present in the Django template context
(passed to `location_lookup.js` today via `data-api-key`). No new
environment variable or server endpoint is needed.

### Picker-specific behavior

- Shows a search bar and "Use my location" button
- On select, calls `onSelect({ name, lat, lon, city, state, place_id })`
- No filter sidebar

### Viewer-specific behavior

- Loads pins from `/api/map/locations/` with current filters
- Shows cluster annotations
- Click a cluster to zoom in
- Click a single pin to show the popup
- Re-fetches pins when map region changes significantly (viewport loading)

---

## Performance and clustering

### Problem

A group with 500+ games at 20 locations is trivial. A future scenario
with many groups, many players, and overlapping venues could produce
hundreds of pins in the same area.

### Client-side clustering

Use the **Supercluster** library (open source, no dependencies).
It accepts GeoJSON points and returns clusters for a given zoom level
and viewport. Google Maps zoom-change events trigger re-clustering.

```
npm install supercluster   (or load from CDN)
```

Supercluster is used in-browser only; no server changes needed for
basic clustering.

### Server-side pre-aggregation (for large datasets)

If pin counts grow large (1,000+ distinct locations), move clustering
to the server. The `/api/map/locations/` endpoint accepts a `zoom`
parameter and returns pre-aggregated cluster centroids with counts
instead of individual pins. This avoids sending large GeoJSON payloads
to the browser.

Implement server-side clustering only when client-side performance
becomes noticeably slow. The threshold is roughly 500+ visible pins
at the same zoom level.

### Viewport loading

The map viewer only fetches pins within the current visible bounding
box plus a margin. As the user pans, new pins are fetched and existing
out-of-viewport pins are removed from the map. This keeps memory and
DOM size bounded.

Endpoint parameter: `?bbox=lon_min,lat_min,lon_max,lat_max`

---

## Privacy model

### Current model

Locations are per-group (each group has its own LocationLibrary).
Members of a group can see all locations in that group's library.
Anonymous/demo users cannot see any location data.

### Proposed extensions

| Scenario | Visibility |
|----------|-----------|
| Group member views map | Sees all geocoded locations for their groups |
| Non-member views a group | No location data (same as today) |
| Demo group | Locations and exact coordinates visible to anonymous visitors; personal home names and addresses are already obfuscated in demo data |
| Admin/staff | Sees all locations across all groups |

### Home address concern

If a game is played at a private residence, precise coordinates are
stored and the pin is shown on the map at full precision. To avoid
exposing identifying address information:

- `street_address` for residential locations stores the street name
  only - no street number and no unit/apartment number (detected via
  reverse geocode `types` field)
- The map pin itself is shown at the stored coordinates; the address
  line displayed in the popup omits the number

---

## Implementation phases

**Deployment priority:** Phase 1 ships to production as soon as it is
complete, before any map UI exists. The goal is to begin accumulating
real coordinate data immediately via the existing Lookup button. Map
display features in later phases depend on that data being present.

### Phase 1 - Schema and data foundation

- Add coordinate and address fields to `Location`
- Migration (nullable fields, no backfill in migration)
- Update Lookup button flow to save coordinates on location create/update
- Update `docs/google-places.md` to note which fields are saved

### Phase 2 - Backfill tool

- `geocode_locations` management command (CLI, interactive)
- Admin action on Location list (modal with mini-map preview)
- Backfill existing seed and demo locations

### Phase 3 - Map picker

- "Set location" modal on game recording form
- Modes: GPS lookup (existing), text search, drop pin
- Base `location_map.js` module (init, destroy, mode switching)
- On confirm: write name + coordinates to location field

### Phase 4 - Map viewer

- `/games/map/` view and template
- `/api/map/locations/` GeoJSON endpoint with filters
- Filter sidebar (group, game type, player, date range, city, state)
- Viewport loading and client-side Supercluster clustering
- Pin popup with game counts and link to filtered game list

### Phase 5 - Custom pins

- HTML pin template per game type using `AdvancedMarkerElement`
- Cluster badge annotation
- Selected/hover states

### Phase 6 - AI integration

- Add location fields to AI game history context rows
- Prompt update noting geographic filter capability
- Test location-aware questions against real data

### Phase 7 - Performance hardening

- Server-side clustering if client-side becomes slow
- Caching GeoJSON responses (invalidate on new game recorded)
- Load testing with realistic pin counts

