# Google Places API - Location Lookup Setup

LeaderLodge uses the Google Places API to let users tap a **Lookup** button next to the Location field when recording a game. The browser detects the device's GPS coordinates, sends a nearby-places search to Google, and shows a short list of venues to pick from.

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

Both are required. The Maps JavaScript API loads the client library. Places API (New) handles the nearby search. The legacy Places API does not accept new customers as of March 2025.

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

7. Under **API restrictions**, select **Restrict key**, then check **Maps JavaScript API** and **Places API (New)** in the list.
8. Click **Save**.

The key now only works from your listed domains and only for the Places API.

---

## Step 6: Add the key locally

Open your `.env` file and add:

```
GOOGLE_PLACES_API_KEY=AIzaSy...your-key-here...
```

Restart `python manage.py runserver`. Open the Record Game page and the **Lookup** button should appear next to the Location label.

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

## Testing the Lookup button

1. Open **Record Game** (`/games/new/`).
2. The **Lookup** button (location pin icon) appears to the right of the **Location** label.
3. Click **Lookup**. The browser asks for location permission - allow it.
4. The button briefly shows **Locating...** then **Searching...**
5. A dropdown of up to 8 nearby establishments appears below the location field.
6. Click any result to fill the location field with that place's name.
7. Submit the form as normal.

If the button does not appear, check:
- `GOOGLE_PLACES_API_KEY` is set in `.env` (local) or Railway Variables (production).
- The server was restarted after adding the key locally.
- You are logged in (the button is hidden for anonymous/demo users).

---

## What Lookup saves (Phase 1)

Nearby search requests Places fields: `displayName`, `addressComponents`,
`location`, and `id`. On submit, the game form posts optional hidden geo
fields with the location name. Those are stored on the group's `Location`
row (not on the Game).

| User action | Saved `lat`/`lon` | `geocode_source` |
|-------------|-------------------|------------------|
| Picks a Places result | Google place geometry | `places_lookup` |
| Picks the city-only row, or types a custom name after Lookup | Device GPS | `gps` |
| Types a name with no Lookup | None (null until reuse or backfill) | (blank) |
| Reuses an existing Location that already has coords | Existing coords unchanged | unchanged |

Phone GPS is used only to find nearby places and as the pin when there is
no Google place point. A Places pick always prefers Google coordinates.

Fields that may be saved: `lat`, `lon`, `city`, `state`, `country`,
`postal_code`, `street_address`, `place_id`, `geocode_source`,
`geocode_at`. See `docs/location-map.md` for the full location map plan.

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

Remove or leave blank `GOOGLE_PLACES_API_KEY` in your environment. When the key is absent, the Lookup button does not render and no Google scripts are loaded.
