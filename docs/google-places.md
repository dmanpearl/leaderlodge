# Google Places API - Location Lookup Setup

LeaderLodge uses the Google Places API on the Record Game location field:

- **Near me** (pin icon next to the label) always runs a nearby search from
  device GPS.
- **Search** (magnifying glass inside the text field, left of clear) runs a
  Places text search on the typed name, with optional GPS bias.
- **Map** opens the shared map picker (search, drop pin, pin lookup, use my
  location) and writes the chosen pin onto the game form.

All three show or fill venues to pick from; Map uses the same modal as Set place.

The API key is a **browser-restricted** key: it is safe to expose in the page source because Google enforces HTTP referrer restrictions on it. It never touches your server after the initial render.

---

## Cost and billing

The Places Nearby Search endpoint costs $0.032 per call. Google provides a **$200/month free credit** that resets each month. At 10 lookups per day, the annual cost is roughly $1.17 - well inside the free credit.

You still need a billing account attached to your Cloud project for the credit to apply. Without one, the API returns `REQUEST_DENIED` errors.

---

## Step 1: Sign in to Google Cloud Console

Go to [https://console.cloud.google.com/](https://console.cloud.google.com/) and sign in.

You can use your Google Workspace account (`dmanpearl@pixelmonks.com`). Google Workspace accounts have full access to Cloud Console. If prompted, choose the personal/consumer context rather than a managed organization, or create the project inside your workspace organization - either works.

---

## Step 2: Create a Cloud project

1. Click the project selector at the top of the page (next to the Google Cloud logo).
2. Click **New Project**.
3. Name it something like `LeaderLodge` and leave Organization as-is.
4. Click **Create** and wait a few seconds for the project to be ready.
5. Make sure the new project is selected in the top selector before continuing.

If you already have a suitable project, select it and skip this step.

---

## Step 3: Enable the required APIs

1. In the left nav, go to **APIs and Services** > **Library**.
2. Search for and enable **Maps JavaScript API**.
3. Search for and enable **Places API (New)**.
4. Search for and enable **Geocoding API** (reverse geocode for map pin assigns).

Both Maps JavaScript API and Places API (New) are required for Near me and Search.
Geocoding API is required for **Set place** when the user drops a pin
without picking a Places result.

---

## Step 4: Enable billing

1. In the left nav, go to **Billing**.
2. If no billing account is linked, click **Link a billing account** and follow the prompts to add a payment method.
3. The $200/month credit covers normal LeaderLodge usage with no actual charges.

---

## Step 5: Create a browser API key

1. Go to **APIs and Services** > **Credentials**.
2. Click **+ Create Credentials** > **API key**.
3. Copy the key (starts with `AIzaSy`). You will add it to your environment next.

**Immediately restrict the key:**

4. Click **Edit API key** (pencil icon next to the new key).
5. Under **Application restrictions**, select **HTTP referrers (websites)**.
6. Add the following referrers (one per line):

   ```
   http://127.0.0.1:8000/*
   http://localhost:8000/*
   https://leaderlodge.com/*
   https://www.leaderlodge.com/*
   ```

   Add `https://*.up.railway.app/*` only if you need to test on a Railway preview URL.

7. Under **API restrictions**, select **Restrict key**, then check **Maps JavaScript API**, **Places API (New)**, and **Geocoding API** in the list.
8. Click **Save**.

The key now only works from your listed domains and for the enabled Maps APIs.

---

## Step 6: Add the key locally

Open your `.env` file and add:

```
GOOGLE_PLACES_API_KEY=AIzaSy...your-key-here...
```

Restart `python manage.py runserver`. Open the Record Game page and the **Near me** button should appear next to the Location label.

---

## Step 7: Add the key to Railway (production)

1. In the Railway dashboard, open your LeaderLodge web service.
2. Go to **Variables**.
3. Add:

   | Variable | Value |
   |----------|-------|
   | `GOOGLE_PLACES_API_KEY` | `AIzaSy...your-key-here...` |

4. Redeploy (Railway redeploys automatically when you save variables).

---

## Testing Near me and Search

1. Open **Record Game** (`/games/new/`).
2. The **Near me** button (location pin icon) appears to the right of the **Location** label.
3. Click **Near me** (with or without text in the field). The browser asks for location permission - allow it.
4. The button briefly shows **Locating...** then a spinner while searching.
5. A dropdown of up to 8 nearby establishments appears below the location field.
6. Click any result to fill the location field with that place's name and Google coordinates.
7. If the venue is missing from nearby results: type a business name (optionally with city). A magnifying-glass **Search** button appears inside the field (left of clear). Click it to run a Places text search (up to 8 results), same idea as **Set place** search on the Locations page.
8. Or click **Map** next to Near me: search / drop pin / pin lookup / use my location, then **Use place** to fill the location name and hidden geo fields on the form.
9. Submit the form as normal.

If the Near me button does not appear, check:
- `GOOGLE_PLACES_API_KEY` is set in `.env` (local) or Railway Variables (production).
- The server was restarted after adding the key locally.
- You are logged in (the button is hidden for anonymous/demo users).

---

## What Near me / Search saves (Phase 1)

Nearby search requests Places fields: `displayName`, `addressComponents`,
`location`, and `id`. On submit, the game form posts optional hidden geo
fields with the location name. Those are stored on the group's `Location`
row (not on the Game).

| User action | Saved `lat`/`lon` | `geocode_source` |
|-------------|-------------------|------------------|
| Picks a Places result | Google place geometry | `places_lookup` (Near me) or `text_search` (in-field Search) |
| Confirms a Map picker selection | Google place or pin geometry | `places_lookup`, `text_search`, or `map_pin` |
| Picks the city-only row, or types a custom name after Near me | Device GPS | `gps` |
| Types a name with no Near me / Search / Map | None (null until reuse or backfill) | (blank) |
| Reuses an existing Location that already has coords | Existing coords unchanged | unchanged |

Phone GPS is used only to find nearby places, bias typed text search, and as
the pin when there is no Google place point. A Places pick always prefers
Google coordinates.

Fields that may be saved: `lat`, `lon`, `city`, `state`, `country`,
`postal_code`, `street_address`, `place_id`, `geocode_source`,
`geocode_at`. See `docs/location-map.md` for the full location map plan.

---

## Set place on map (Phase 2a)

Group managers can open **Set place** from **Edit game**, **Game detail**
(when a location is set), or the group **Locations** list. The modal
includes:

- Editable Places text search (pre-filled from the informal location name)
- Map with draggable pin (click map to drop)
- **Pin lookup** (nearby Places at the pin, same types as Near me)
- Optional **Use my location** (centers map; not the default for assign)
- **Assign** writes geo to the `Location` row for all games using it

| User action | `geocode_source` |
|-------------|------------------|
| Picks a Places search or pin-lookup result | `text_search` or `places_lookup` |
| Drops pin only (reverse geocode) | `map_pin` |
| Use my location then pin lookup | `gps` or `places_lookup` |

Assign replaces existing coords only after confirm. Optional **Use place
name** renames the location to the Google place display name.

---

## Games Map viewer (Phase 4)

`/games/map/` shows geocoded venues for a visible group (navbar **Map**).
Anonymous visitors can use it for the **Demo** group when demo mode is on.
Filters: group, game type, player, period, state, city, location name.
Pins cluster via Supercluster; popups link to the games list for that venue.
GeoJSON: `GET /api/map/locations/` with the same query params.

Leaderboards add a **Location** venue filter that uses existing
`location_id` ranking support.

Server endpoint: `POST /groups/<group_id>/locations/<location_id>/set-place/`
(JSON geo payload).

---

## Interactive CLI backfill (optional)

For cleaning hundreds of historical names, use an interactive management
command that mirrors **Map > Search > Assign**, with accept/reject per row:

```bash
python manage.py backfill_location_places \
  --group manpearl \
  --skip-file /tmp/manpearl_place_skips.json \
  --limit 40
```

Prompts for each ungeocoded location:

| Input | Action |
|-------|--------|
| `1` .. `N` | Assign that Places result; **keep** the informal location name |
| `1a` .. `Na` | Assign and **adopt** the Google place display name |
| `/Cafe 50s Venice` | Re-search with a better query |
| `s` | Skip and remember in `--skip-file` (resume later) |
| `n` | Skip once (not remembered) |
| `q` | Quit |

Requires `GOOGLE_PLACES_SERVER_API_KEY`: a **server** Places key (IP-restricted
or unrestricted). The browser-restricted `GOOGLE_PLACES_API_KEY` usually
returns `REQUEST_DENIED` from `manage.py` because of HTTP referrer rules.

Successful assigns set `geocode_source=backfill_confirmed`.

Add `--dry-run` to practice without writing. Add `--include-geocoded` to
revisit rows that already have pins.

---

## Troubleshooting

**Button appears but lookup fails with "Location lookup failed."**

- Open browser DevTools (Network tab) and look for a Google Maps script load error.
- Verify the key is correctly pasted (no extra spaces).
- Check that the referrer restriction includes `http://127.0.0.1:8000/*` for local testing.

**"Location permission denied."**

- The user clicked **Block** on the browser geolocation prompt.
- On iOS Safari, go to **Settings** > **Safari** > **Location** and allow the site.
- On desktop Chrome, click the lock icon in the address bar and reset location permission.

**"REQUEST_DENIED" in browser console**

- Billing is not enabled on the Cloud project. See Step 4.
- Or the referrer restriction blocks the current domain. Double-check the allowed-referrers list in Cloud Console.

**Dropdown shows generic places (hotels, shops) instead of game venues**

This is expected behavior for the initial release. The Places API returns general establishments near the GPS coordinates. A filtering step that prioritizes the group's known locations will be added in a future release.

---

## Removing or disabling the feature

Remove or leave blank `GOOGLE_PLACES_API_KEY` in your environment. When the key is absent, the Near me, Search, and Map controls do not render and no Google scripts are loaded.
