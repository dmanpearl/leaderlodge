(function () {
  const btn = document.getElementById("location-lookup-btn");
  if (!btn) return;

  const searchBtn = document.querySelector("[data-location-search]");

  let mapsPromise = null;
  let lastDeviceCoords = null;
  let lastFilledValue = null;
  let lookupList = null;
  let activeControl = null;

  function loadGoogleMaps(apiKey) {
    if (mapsPromise) return mapsPromise;
    mapsPromise = new Promise((resolve, reject) => {
      let settled = false;

      const finish = (err) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (err) {
          mapsPromise = null;
          reject(err);
        } else {
          resolve();
        }
      };

      const timer = setTimeout(
        () => finish(new Error("Google Maps load timed out.")),
        15000,
      );

      const prevAuthFailure = window.gm_authFailure;
      window.gm_authFailure = () => {
        window.gm_authFailure = prevAuthFailure;
        finish(
          new Error(
            "Google Maps API key error. Check key and referrer restrictions.",
          ),
        );
        if (prevAuthFailure) prevAuthFailure();
      };

      const script = document.createElement("script");
      script.src =
        `https://maps.googleapis.com/maps/api/js` +
        `?key=${encodeURIComponent(apiKey)}&loading=async`;
      script.async = true;
      script.onload = () => {
        /* With loading=async the bootstrap executes synchronously, but
           google.maps.importLibrary may not be wired up yet on the first call.
           Poll briefly until it is available before resolving. */
        const start = Date.now();
        const poll = setInterval(() => {
          if (typeof google?.maps?.importLibrary === "function") {
            clearInterval(poll);
            finish(null);
          } else if (Date.now() - start > 5000) {
            clearInterval(poll);
            finish(new Error("Google Maps init timed out."));
          }
        }, 30);
      };
      script.onerror = () => finish(new Error("Google Maps failed to load."));
      document.head.appendChild(script);
    });
    return mapsPromise;
  }

  function getPosition() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Geolocation is not supported."));
        return;
      }
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 60000,
      });
    });
  }

  function geoRoot() {
    return document.querySelector("[data-location-field]");
  }

  function geoInput(key) {
    return geoRoot()?.querySelector(`[data-location-geo="${key}"]`);
  }

  function setGeoFields(geo) {
    const mapping = {
      lat: geo?.lat ?? "",
      lon: geo?.lon ?? "",
      city: geo?.city ?? "",
      state: geo?.state ?? "",
      country: geo?.country ?? "",
      postal_code: geo?.postal_code ?? "",
      street_address: geo?.street_address ?? "",
      place_id: geo?.place_id ?? "",
      geocode_source: geo?.geocode_source ?? "",
    };
    for (const [key, value] of Object.entries(mapping)) {
      const input = geoInput(key);
      if (input) input.value = value === null || value === undefined ? "" : value;
    }
    document.dispatchEvent(new CustomEvent("location-geo-change"));
  }

  function clearGeoFields() {
    setGeoFields(null);
    lastFilledValue = null;
  }

  function setPhoneGpsGeo(city, state, country) {
    if (!lastDeviceCoords) {
      clearGeoFields();
      return;
    }
    setGeoFields({
      lat: lastDeviceCoords.lat,
      lon: lastDeviceCoords.lon,
      city: city || "",
      state: state || "",
      country: country || "",
      postal_code: "",
      street_address: "",
      place_id: "",
      geocode_source: "gps",
    });
  }

  function extractAddressParts(addressComponents) {
    const parts = {
      city: "",
      state: "",
      country: "",
      postal_code: "",
      street_address: "",
    };
    if (!addressComponents) return parts;

    let route = "";
    let streetNumber = "";
    for (const c of addressComponents) {
      const types = c.types || [];
      if (types.includes("locality")) {
        parts.city = c.longText || c.shortText || "";
      } else if (types.includes("administrative_area_level_1")) {
        parts.state = c.shortText || "";
      } else if (types.includes("country")) {
        parts.country = (c.shortText || "").toUpperCase();
      } else if (types.includes("postal_code")) {
        parts.postal_code = c.longText || c.shortText || "";
      } else if (types.includes("route")) {
        route = c.longText || c.shortText || "";
      } else if (types.includes("street_number")) {
        streetNumber = c.longText || c.shortText || "";
      }
    }
    // Prefer street name only for stored street_address.
    parts.street_address = route || (streetNumber ? streetNumber : "");
    return parts;
  }

  function extractCityState(addressComponents) {
    const parts = extractAddressParts(addressComponents);
    if (parts.city && parts.state) return `${parts.city}, ${parts.state}`;
    return parts.city || parts.state || null;
  }

  function placeLatLon(place) {
    const loc = place?.location;
    if (!loc) return null;
    const lat = typeof loc.lat === "function" ? loc.lat() : loc.lat;
    const lng = typeof loc.lng === "function" ? loc.lng() : loc.lng;
    if (lat == null || lng == null) return null;
    return { lat: Number(lat), lon: Number(lng) };
  }

  function placeIdOf(place) {
    return place?.id || place?.placeId || "";
  }

  const PLACE_FIELDS = ["displayName", "addressComponents", "location", "id"];
  const MAX_PLACE_RESULTS = 8;

  async function nearbySearch(lat, lng) {
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Places search timed out.")), 10000),
    );
    const searchPromise = (async () => {
      const { Place } = await google.maps.importLibrary("places");
      const { places } = await Place.searchNearby({
        fields: PLACE_FIELDS,
        locationRestriction: { center: { lat, lng }, radius: 600 },
        includedTypes: [
          "park",
          "restaurant",
          "cafe",
          "community_center",
          "shopping_mall",
          "library",
          "sports_complex",
          "athletic_field",
          "campground",
          "rv_park",
          "tourist_attraction",
          "zoo",
          "aquarium",
          "museum",
          "hospital",
          "food_court",
        ],
        maxResultCount: MAX_PLACE_RESULTS,
      });
      return places || [];
    })();
    return Promise.race([searchPromise, timeoutPromise]);
  }

  async function textSearch(query, biasCoords) {
    const text = String(query || "").trim();
    if (!text) {
      throw new Error("Enter a place name to search.");
    }
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Places search timed out.")), 12000),
    );
    const searchPromise = (async () => {
      const { Place } = await google.maps.importLibrary("places");
      const request = {
        textQuery: text,
        fields: PLACE_FIELDS,
        maxResultCount: MAX_PLACE_RESULTS,
      };
      if (biasCoords?.lat != null && biasCoords?.lon != null) {
        // Maps JS expects a Circle/LatLng, not the REST {circle:{center,radius}} shape.
        request.locationBias = new google.maps.Circle({
          center: { lat: Number(biasCoords.lat), lng: Number(biasCoords.lon) },
          radius: 5000,
        });
      }
      const { places } = await Place.searchByText(request);
      return places || [];
    })();
    return Promise.race([searchPromise, timeoutPromise]);
  }

  function hideList() {
    lookupList?.remove();
    lookupList = null;
  }

  function locationInput() {
    return (
      document.querySelector("[data-location-autocomplete]") ??
      document.querySelector("[data-location-field] input[type=text]")
    );
  }

  function fillLocation(value) {
    const input = locationInput();
    if (!input) return;
    input.value = value;
    lastFilledValue = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function addListItem(items, fillValue, label, meta) {
    items.push({ fillValue, label, meta });
  }

  function applySelection(item) {
    fillLocation(item.fillValue);
    const meta = item.meta || {};
    if (meta.kind === "place" && meta.lat != null && meta.lon != null) {
      setGeoFields({
        lat: meta.lat,
        lon: meta.lon,
        city: meta.city || "",
        state: meta.state || "",
        country: meta.country || "",
        postal_code: meta.postal_code || "",
        street_address: meta.street_address || "",
        place_id: meta.place_id || "",
        geocode_source: meta.geocode_source || "places_lookup",
      });
    } else {
      // City-only row, or Places result missing geometry: phone GPS.
      setPhoneGpsGeo(meta.city, meta.state, meta.country);
    }
    hideList();
    btn.focus();
  }

  function showList(places, options) {
    const mode = options?.mode || "nearby";
    const query = options?.query || "";
    hideList();
    if (!places.length) {
      if (mode === "text") {
        showError(
          "No places found for that name. Try a fuller name or city.",
        );
      } else {
        showError(
          "No nearby places found. Type a name, then use the search icon.",
        );
      }
      return;
    }

    const wrap = document.querySelector(
      "[data-location-field] .combobox-input-wrap",
    );
    if (!wrap) return;

    lookupList = document.createElement("ul");
    lookupList.className = "location-lookup-list";
    lookupList.setAttribute("role", "listbox");
    lookupList.setAttribute(
      "aria-label",
      mode === "text" ? "Place search results" : "Nearby places",
    );
    wrap.appendChild(lookupList);

    const items = [];
    const placeSource = mode === "text" ? "text_search" : "places_lookup";

    if (mode === "nearby") {
      const cityState = extractCityState(places[0].addressComponents);
      const firstParts = extractAddressParts(places[0].addressComponents);
      if (cityState) {
        addListItem(items, cityState, cityState, {
          kind: "city",
          city: firstParts.city,
          state: firstParts.state,
          country: firstParts.country,
        });
      }
    }

    for (const place of places) {
      const name =
        typeof place.displayName === "string"
          ? place.displayName
          : place.displayName?.text || "";
      const parts = extractAddressParts(place.addressComponents);
      const cs = extractCityState(place.addressComponents);
      const coords = placeLatLon(place);
      addListItem(
        items,
        cs ? `${name}, ${cs}` : name,
        cs ? `${name}, ${cs}` : name,
        {
          kind: "place",
          lat: coords?.lat,
          lon: coords?.lon,
          city: parts.city,
          state: parts.state,
          country: parts.country,
          postal_code: parts.postal_code,
          street_address: parts.street_address,
          place_id: placeIdOf(place),
          geocode_source: placeSource,
        },
      );
    }

    items.forEach((item, i) => {
      const li = document.createElement("li");
      li.className = "location-lookup-option";
      li.setAttribute("role", "option");
      li.setAttribute("tabindex", "0");

      const nameEl = document.createElement("span");
      nameEl.className = "location-lookup-name";
      nameEl.textContent = item.label;
      li.appendChild(nameEl);

      li.addEventListener("mousedown", (e) => e.preventDefault());
      li.addEventListener("click", () => applySelection(item));
      li.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          applySelection(item);
        } else if (e.key === "ArrowDown") {
          e.preventDefault();
          lookupList?.children[i + 1]?.focus();
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          const prev = lookupList?.children[i - 1];
          if (prev) prev.focus();
          else btn.focus();
        } else if (e.key === "Escape") {
          e.preventDefault();
          hideList();
          btn.focus();
        }
      });

      lookupList.appendChild(li);
    });

    lookupList.children[0]?.focus();
  }

  document.addEventListener("click", (e) => {
    if (
      lookupList &&
      !lookupList.contains(e.target) &&
      e.target !== btn &&
      !e.target.closest("[data-location-search]")
    ) {
      hideList();
    }
  });

  function setLookupButtonIcon(state) {
    const existing = btn.querySelector("i, .location-lookup-spinner");
    if (existing) existing.remove();

    if (state === "searching" && activeControl === "nearby") {
      const spinner = document.createElement("span");
      spinner.className =
        "spinner-border spinner-border-sm location-lookup-spinner";
      spinner.setAttribute("aria-hidden", "true");
      btn.prepend(spinner);
    } else {
      const icon = document.createElement("i");
      icon.className = "bi bi-geo-alt-fill";
      icon.setAttribute("aria-hidden", "true");
      btn.prepend(icon);
    }

    const text = btn.querySelector(".location-lookup-btn-text");
    if (text) {
      const busy = state !== "idle" && activeControl === "nearby";
      text.hidden = state === "searching" && activeControl === "nearby";
      text.textContent =
        busy && state === "locating" ? "Locating..." : "Near me";
    }
  }

  function setSearchButtonIcon(state) {
    if (!searchBtn) return;
    const existing = searchBtn.querySelector("i, .location-lookup-spinner");
    if (existing) existing.remove();

    if (
      (state === "locating" || state === "searching") &&
      activeControl === "text"
    ) {
      const spinner = document.createElement("span");
      spinner.className =
        "spinner-border spinner-border-sm location-lookup-spinner";
      spinner.setAttribute("aria-hidden", "true");
      searchBtn.appendChild(spinner);
    } else {
      const icon = document.createElement("i");
      icon.className = "bi bi-search";
      icon.setAttribute("aria-hidden", "true");
      searchBtn.appendChild(icon);
    }
  }

  function setButtonState(state, control) {
    if (control) {
      activeControl = control;
    }
    if (state === "idle") {
      activeControl = null;
    }

    const busy = state !== "idle";
    btn.disabled = busy;
    if (searchBtn) searchBtn.disabled = busy;

    setLookupButtonIcon(state);
    setSearchButtonIcon(state);
  }

  let errEl = null;

  function showError(msg) {
    errEl?.remove();
    errEl = document.createElement("span");
    errEl.className = "location-lookup-error text-danger small ms-2";
    btn.after(errEl);
    errEl.textContent = msg;
    console.warn("[location-lookup]", msg);
    setTimeout(() => {
      errEl?.remove();
      errEl = null;
    }, 5000);
  }

  function onLocationInputChanged() {
    const input = locationInput();
    if (!input) return;
    const value = input.value.trim();
    if (!value) {
      clearGeoFields();
      return;
    }
    if (lastFilledValue !== null && value === lastFilledValue) {
      return;
    }
    // Custom or edited name after Lookup: phone GPS when available.
    if (lastDeviceCoords) {
      setPhoneGpsGeo("", "", "");
      lastFilledValue = value;
    } else {
      clearGeoFields();
    }
  }

  const inputEl = locationInput();
  if (inputEl) {
    inputEl.addEventListener("input", onLocationInputChanged);
  }

  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-location-clear]")) {
      clearGeoFields();
    }
  });

  // Map picker (record mode) wrote geo + name; treat as intentional fill.
  document.addEventListener("location-map-apply", (e) => {
    const name = String(e.detail?.name || "").trim();
    lastFilledValue = name || null;
  });

  // Autocomplete library pick: reuse saved coords when present, else clear Lookup geo.
  document.addEventListener("location-autocomplete-select", (event) => {
    const name = String(event.detail?.name || "").trim();
    const geo = event.detail?.geo;
    if (geo?.lat != null && geo?.lon != null) {
      setGeoFields(geo);
      lastFilledValue = name || null;
      return;
    }
    clearGeoFields();
    lastFilledValue = name || null;
  });

  async function runPlacesLookup(mode) {
    if (lookupList) {
      hideList();
      return;
    }
    errEl?.remove();
    errEl = null;

    const apiKey = btn.dataset.apiKey;
    if (!apiKey) return;

    const query = (locationInput()?.value || "").trim();
    if (mode === "text" && !query) {
      showError("Enter a place name to search.");
      return;
    }

    setButtonState("locating", mode);

    try {
      // Prefer GPS for nearby search and as a bias for typed text search.
      try {
        const pos = await getPosition();
        lastDeviceCoords = {
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
        };
      } catch (geoErr) {
        if (mode === "nearby") {
          throw geoErr;
        }
        // Text search can still run without GPS.
      }

      setButtonState("searching", mode);
      await loadGoogleMaps(apiKey);

      let places;
      if (mode === "text") {
        places = await textSearch(query, lastDeviceCoords);
      } else {
        places = await nearbySearch(
          lastDeviceCoords.lat,
          lastDeviceCoords.lon,
        );
      }
      setButtonState("idle");
      showList(places, { mode, query });
    } catch (err) {
      setButtonState("idle");
      let msg = err?.message || "Location lookup failed.";
      if (err?.code === 1) msg = "Location permission denied.";
      else if (err?.code === 2) msg = "Location unavailable.";
      else if (err?.code === 3) msg = "Location request timed out.";
      console.warn("[location-lookup]", err);
      showError(msg);
    }
  }

  btn.addEventListener("click", () => {
    runPlacesLookup("nearby");
  });

  if (searchBtn) {
    searchBtn.addEventListener("mousedown", (event) => {
      event.preventDefault();
    });
    searchBtn.addEventListener("click", () => {
      runPlacesLookup("text");
    });
  }
})();
