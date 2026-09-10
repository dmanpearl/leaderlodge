(function () {
  const modalEl = document.getElementById("location-set-place-modal");
  if (!modalEl || !window.LeaderLodgeLocationMap) return;

  const { LocationMapPicker, formatPlaceLabel } = window.LeaderLodgeLocationMap;

  const subtitleEl = document.getElementById("location-set-place-subtitle");
  const searchInput = document.getElementById("location-map-search-input");
  const searchBtn = document.getElementById("location-map-search-btn");
  const pinLookupBtn = document.getElementById("location-map-pin-lookup-btn");
  const myLocationBtn = document.getElementById("location-map-my-location-btn");
  const mapCanvas = document.getElementById("location-map-canvas");
  const statusEl = document.getElementById("location-map-status");
  const resultsEl = document.getElementById("location-map-results");
  const selectedEl = document.getElementById("location-map-selected");
  const adoptNameCheckbox = document.getElementById("location-map-adopt-name");
  const clearBtn = document.getElementById("location-map-clear-btn");
  const assignBtn = document.getElementById("location-map-assign-btn");
  const titleEl = document.getElementById("location-set-place-modal-label");
  const setPlaceForm = document.getElementById("location-set-place-form");

  const apiKey = modalEl.dataset.apiKey || "";
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

  function refreshPageGet() {
    // Prefer GET navigation over reload(): if Edit game was a failed POST
    // response, reload() would re-POST and show "change at least one…".
    const url = window.location.pathname + window.location.search;
    try {
      window.sessionStorage.setItem(
        "leaderlodge.restoreScroll",
        JSON.stringify({
          path: url,
          y: window.scrollY || window.pageYOffset || 0,
        }),
      );
    } catch (_err) {
      /* ignore quota / private mode */
    }
    window.location.assign(url);
  }

  let picker = null;
  let activeContext = null;
  let pendingPlaces = [];

  function csrfToken() {
    return (
      document.querySelector('input[name="csrfmiddlewaretoken"]')?.value ||
      (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ||
      ""
    );
  }

  function setStatus(message, isError) {
    statusEl.textContent = message || "";
    statusEl.classList.toggle("text-danger", Boolean(isError));
    statusEl.classList.toggle("text-muted", !isError && Boolean(message));
  }

  function setBusy(busy) {
    searchBtn.disabled = busy;
    pinLookupBtn.disabled = busy;
    myLocationBtn.disabled = busy;
    assignBtn.disabled = busy || !picker?.selection;
  }

  function renderSelected(geo) {
    if (!geo) {
      selectedEl.innerHTML =
        '<span class="text-muted">Drop a pin or search, then pick a place.</span>';
      assignBtn.disabled = true;
      adoptNameCheckbox.checked = false;
      adoptNameCheckbox.disabled = true;
      return;
    }
    const label = geo.label || geo.place_display_name || `${geo.lat}, ${geo.lon}`;
    selectedEl.textContent = `Selected: ${label}`;
    assignBtn.disabled = false;
    adoptNameCheckbox.disabled = !geo.place_display_name;
    if (!geo.place_display_name) {
      adoptNameCheckbox.checked = false;
    }
  }

  function hideResults() {
    resultsEl.hidden = true;
    resultsEl.innerHTML = "";
    pendingPlaces = [];
  }

  function showResults(places, source) {
    pendingPlaces = places;
    resultsEl.innerHTML = "";
    places.forEach((place, index) => {
      const li = document.createElement("li");
      li.className = "location-map-result";
      li.setAttribute("role", "option");
      li.textContent = formatPlaceLabel(place);
      li.addEventListener("click", () => {
        try {
          picker.selectPlace(place, source);
          hideResults();
        } catch (err) {
          setStatus(err?.message || "Could not select place.", true);
        }
      });
      if (index === 0) {
        li.classList.add("location-map-result--active");
      }
      resultsEl.appendChild(li);
    });
    resultsEl.hidden = false;
    picker.showResultMarkers(places, (place) => {
      try {
        picker.selectPlace(place, source);
        hideResults();
      } catch (err) {
        setStatus(err?.message || "Could not select place.", true);
      }
    });
  }

  function resetModal() {
    hideResults();
    setStatus("");
    adoptNameCheckbox.checked = false;
    adoptNameCheckbox.disabled = true;
    renderSelected(null);
    setAssignButtonLabel("assign");
    myLocationBtn.classList.remove("text-primary");
    if (picker) {
      picker.destroy();
      picker = null;
    }
    activeContext = null;
  }

  async function ensurePicker(initial) {
    if (picker) {
      picker.destroy();
      picker = null;
    }
    mapCanvas.innerHTML = "";
    picker = new LocationMapPicker(mapCanvas, {
      apiKey,
      onSelectionChange: renderSelected,
      onStatus: setStatus,
    });
    setBusy(true);
    try {
      await picker.init(initial);
    } finally {
      setBusy(false);
    }
  }

  function gameCountLabel(count) {
    const n = Number(count) || 0;
    if (n === 1) return "1 game";
    return `${n} games`;
  }

  function setAssignButtonLabel(mode) {
    assignBtn.textContent = mode === "record" ? "Use place" : "Assign";
  }

  function locationNameInput() {
    return (
      document.querySelector("[data-location-autocomplete]") ??
      document.querySelector("[data-location-field] input[type=text]")
    );
  }

  function setFormGeoField(key, value) {
    const input = document.querySelector(
      `[data-location-field] [data-location-geo="${key}"]`,
    );
    if (input) {
      input.value = value === null || value === undefined ? "" : String(value);
    }
  }

  function applyRecordSelection(geo, adoptName) {
    if (!geo) return;

    setFormGeoField("lat", geo.lat);
    setFormGeoField("lon", geo.lon);
    setFormGeoField("city", geo.city || "");
    setFormGeoField("state", geo.state || "");
    setFormGeoField("country", geo.country || "");
    setFormGeoField("postal_code", geo.postal_code || "");
    setFormGeoField("street_address", geo.street_address || "");
    setFormGeoField("place_id", geo.place_id || "");
    setFormGeoField("geocode_source", geo.geocode_source || "map_pin");

    const input = locationNameInput();
    let name = (input?.value || "").trim();
    if (adoptName && geo.place_display_name) {
      name = geo.label || geo.place_display_name;
    } else if (!name && geo.place_display_name) {
      name = geo.label || geo.place_display_name;
    } else if (!name && geo.label && !String(geo.label).match(/^-?\d+(\.\d+)?,\s*-?\d+/)) {
      name = geo.label;
    }
    if (input && name) {
      input.value = name;
    }

    document.dispatchEvent(
      new CustomEvent("location-map-apply", {
        detail: {
          name: input?.value || name || "",
          lat: geo.lat,
          lon: geo.lon,
        },
      }),
    );
    document.dispatchEvent(new CustomEvent("location-geo-change"));
    if (input) {
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  async function openSetPlace(context) {
    if (!apiKey) return;
    activeContext = context;
    const mode = context.mode === "record" ? "record" : "assign";
    activeContext.mode = mode;

    const name = context.locationName || "Location";
    if (mode === "record") {
      titleEl.textContent = "Set location";
      subtitleEl.textContent =
        "Search, drop a pin, or use your location. Confirm writes the pin onto this game.";
      myLocationBtn.classList.add("text-primary");
    } else {
      const count = Number(context.gameCount) || 0;
      titleEl.textContent = `Set place for ${name}`;
      subtitleEl.textContent =
        count > 0
          ? `Updates the location row used by ${gameCountLabel(count)}.`
          : "Updates this location row for all linked games.";
      myLocationBtn.classList.remove("text-primary");
    }
    setAssignButtonLabel(mode);
    searchInput.value = name === "Location" ? "" : name;
    adoptNameCheckbox.checked = false;

    const initial = {
      lat: context.lat != null && context.lat !== "" ? Number(context.lat) : null,
      lon: context.lon != null && context.lon !== "" ? Number(context.lon) : null,
    };

    modal.show();
    try {
      await ensurePicker(initial);
    } catch (err) {
      setStatus(err?.message || "Could not load map.", true);
    }
  }

  function buildPayload(confirmReplace) {
    const geo = picker.selection;
    return {
      lat: geo.lat,
      lon: geo.lon,
      city: geo.city || "",
      state: geo.state || "",
      country: geo.country || "",
      postal_code: geo.postal_code || "",
      street_address: geo.street_address || "",
      place_id: geo.place_id || "",
      geocode_source: geo.geocode_source || "map_pin",
      place_display_name: geo.place_display_name || "",
      adopt_place_name: adoptNameCheckbox.checked,
      confirm_replace: confirmReplace,
    };
  }

  async function postAssign(confirmReplace) {
    const response = await fetch(activeContext.setPlaceUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      credentials: "same-origin",
      body: JSON.stringify(buildPayload(confirmReplace)),
    });
    const data = await response.json().catch(() => ({}));
    return { response, data };
  }

  async function handleAssign() {
    if (!activeContext || !picker?.selection) return;

    if (activeContext.mode === "record") {
      applyRecordSelection(picker.selection, adoptNameCheckbox.checked);
      modal.hide();
      return;
    }

    setBusy(true);
    setStatus("");
    try {
      let { response, data } = await postAssign(false);

      if (response.status === 409 && data.error === "confirm_required") {
        const count = data.game_count || activeContext.gameCount || 0;
        const ok = window.confirm(
          `This location already has a pin. Replace it for ${gameCountLabel(count)}?`,
        );
        if (!ok) {
          return;
        }
        ({ response, data } = await postAssign(true));
      }

      if (!response.ok) {
        setStatus(data.error || data.message || "Could not assign place.", true);
        return;
      }

      modal.hide();
      if (typeof activeContext.onSuccess === "function") {
        activeContext.onSuccess(data.location);
      } else {
        refreshPageGet();
      }
    } catch (_err) {
      setStatus("Could not assign place. Please try again.", true);
    } finally {
      setBusy(false);
    }
  }

  async function runSearch(e) {
    if (e) e.preventDefault();
    if (!picker) return;
    setBusy(true);
    hideResults();
    try {
      const places = await picker.searchPlaces(searchInput.value);
      showResults(places, "text_search");
    } catch (err) {
      setStatus(err?.message || "Search failed.", true);
    } finally {
      setBusy(false);
    }
  }

  if (setPlaceForm) {
    setPlaceForm.addEventListener("submit", runSearch);
  } else {
    searchBtn.addEventListener("click", runSearch);
  }

  assignBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    handleAssign();
  });

  pinLookupBtn.addEventListener("click", async () => {
    if (!picker) return;
    setBusy(true);
    hideResults();
    try {
      const places = await picker.pinLookup();
      showResults(places, "places_lookup");
    } catch (err) {
      setStatus(err?.message || "Pin lookup failed.", true);
    } finally {
      setBusy(false);
    }
  });

  myLocationBtn.addEventListener("click", async () => {
    if (!picker) return;
    setBusy(true);
    hideResults();
    try {
      await picker.useMyLocation();
    } catch (err) {
      let msg = err?.message || "Could not get your location.";
      if (err?.code === 1) msg = "Location permission denied.";
      else if (err?.code === 2) msg = "Location unavailable.";
      else if (err?.code === 3) msg = "Location request timed out.";
      setStatus(msg, true);
    } finally {
      setBusy(false);
    }
  });

  clearBtn.addEventListener("click", () => {
    if (!picker) return;
    picker.clearSelection();
    hideResults();
    setStatus("");
  });

  modalEl.addEventListener("hidden.bs.modal", resetModal);

  modalEl.addEventListener("shown.bs.modal", () => {
    searchInput.focus();
    if (picker?.map) {
      google.maps.event.trigger(picker.map, "resize");
      const pos = picker.marker?.getPosition();
      if (pos) {
        picker.map.panTo(pos);
      }
    }
  });

  document.querySelectorAll("[data-location-set-place]").forEach((btn) => {
    btn.addEventListener("click", () => {
      openSetPlace({
        mode: "assign",
        setPlaceUrl: btn.dataset.setPlaceUrl,
        locationName: btn.dataset.locationName,
        gameCount: btn.dataset.gameCount,
        lat: btn.dataset.lat,
        lon: btn.dataset.lon,
        onSuccess: btn.dataset.reload === "false" ? null : undefined,
      });
    });
  });

  document.querySelectorAll("[data-location-record-place]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = locationNameInput();
      const latEl = document.querySelector(
        '[data-location-field] [data-location-geo="lat"]',
      );
      const lonEl = document.querySelector(
        '[data-location-field] [data-location-geo="lon"]',
      );
      openSetPlace({
        mode: "record",
        locationName: (input?.value || "").trim(),
        lat: latEl?.value || "",
        lon: lonEl?.value || "",
      });
    });
  });

  window.LeaderLodgeSetPlace = { open: openSetPlace };
})();
