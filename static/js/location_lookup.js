(function () {
  const btn = document.getElementById("location-lookup-btn");
  if (!btn) return;

  let mapsPromise = null;

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

  function extractCityState(addressComponents) {
    if (!addressComponents) return null;
    let city = "";
    let state = "";
    for (const c of addressComponents) {
      const types = c.types || [];
      if (types.includes("locality")) city = c.longText || c.shortText || "";
      if (types.includes("administrative_area_level_1"))
        state = c.shortText || "";
    }
    if (city && state) return `${city}, ${state}`;
    return city || state || null;
  }

  async function nearbySearch(lat, lng) {
    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Places search timed out.")), 10000),
    );
    const searchPromise = (async () => {
      const { Place } = await google.maps.importLibrary("places");
      const { places } = await Place.searchNearby({
        fields: ["displayName", "addressComponents"],
        locationRestriction: { center: { lat, lng }, radius: 800 },
        maxResultCount: 8,
      });
      return places || [];
    })();
    return Promise.race([searchPromise, timeoutPromise]);
  }

  let lookupList = null;

  function hideList() {
    lookupList?.remove();
    lookupList = null;
  }

  function fillLocation(value) {
    const input =
      document.querySelector("[data-location-autocomplete]") ??
      document.querySelector("[data-location-field] input[type=text]");
    if (!input) return;
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function addListItem(items, fillValue, label, isCity) {
    items.push({ fillValue, label, isCity });
  }

  function showList(places) {
    hideList();
    if (!places.length) {
      showError("No nearby places found.");
      return;
    }

    const wrap = document.querySelector(
      "[data-location-field] .combobox-input-wrap",
    );
    if (!wrap) return;

    lookupList = document.createElement("ul");
    lookupList.className = "location-lookup-list";
    lookupList.setAttribute("role", "listbox");
    lookupList.setAttribute("aria-label", "Nearby places");
    wrap.appendChild(lookupList);

    const items = [];

    const cityState = extractCityState(places[0].addressComponents);
    if (cityState) addListItem(items, cityState, cityState, true);

    for (const place of places) {
      const name = place.displayName;
      const cs = extractCityState(place.addressComponents);
      addListItem(items, cs ? `${name}, ${cs}` : name, cs ? `${name}, ${cs}` : name, false);
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
      li.addEventListener("click", () => {
        fillLocation(item.fillValue);
        hideList();
        btn.focus();
      });
      li.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          fillLocation(item.fillValue);
          hideList();
          btn.focus();
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
    if (lookupList && !lookupList.contains(e.target) && e.target !== btn) {
      hideList();
    }
  });

  function setButtonState(state) {
    btn.disabled = state !== "idle";

    const existing = btn.querySelector("i, .location-lookup-spinner");
    if (existing) existing.remove();

    if (state === "searching") {
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
      text.hidden = state === "searching";
      text.textContent = state === "locating" ? "Locating..." : "Lookup";
    }
  }

  let errEl = null;

  function showError(msg) {
    errEl?.remove();
    errEl = document.createElement("span");
    errEl.className = "location-lookup-error text-danger small ms-2";
    btn.after(errEl);
    errEl.textContent = msg;
    setTimeout(() => {
      errEl?.remove();
      errEl = null;
    }, 5000);
  }

  btn.addEventListener("click", async () => {
    if (lookupList) {
      hideList();
      return;
    }
    errEl?.remove();
    errEl = null;

    const apiKey = btn.dataset.apiKey;
    if (!apiKey) return;

    setButtonState("locating");

    try {
      const pos = await getPosition();
      setButtonState("searching");
      await loadGoogleMaps(apiKey);
      const places = await nearbySearch(
        pos.coords.latitude,
        pos.coords.longitude,
      );
      setButtonState("idle");
      showList(places);
    } catch (err) {
      setButtonState("idle");
      let msg = err?.message || "Location lookup failed.";
      if (err?.code === 1) msg = "Location permission denied.";
      else if (err?.code === 2) msg = "Location unavailable.";
      else if (err?.code === 3) msg = "Location request timed out.";
      showError(msg);
    }
  });
})();
