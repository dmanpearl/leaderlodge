/**
 * Live pin status for location fields: green badge when hidden lat/lon are set.
 */
(function () {
  const statusRoot = document.querySelector("[data-location-pin-status]");
  if (!statusRoot) return;

  const badgeEl = statusRoot.querySelector("[data-location-pin-badge]");
  const emptyEl = statusRoot.querySelector("[data-location-pin-empty]");
  if (!badgeEl || !emptyEl) return;

  function geoInput(key) {
    return document.querySelector(`[data-location-field] [data-location-geo="${key}"]`);
  }

  function hasPinCoords() {
    const latRaw = geoInput("lat")?.value ?? "";
    const lonRaw = geoInput("lon")?.value ?? "";
    if (latRaw === "" || lonRaw === "") return false;
    const lat = Number(latRaw);
    const lon = Number(lonRaw);
    return Number.isFinite(lat) && Number.isFinite(lon);
  }

  function refreshPinStatus() {
    const pinned = hasPinCoords();
    badgeEl.classList.toggle("d-none", !pinned);
    emptyEl.classList.toggle("d-none", pinned);
  }

  document.addEventListener("location-map-apply", refreshPinStatus);
  document.addEventListener("location-geo-change", refreshPinStatus);
  document.addEventListener("location-autocomplete-select", refreshPinStatus);

  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-location-clear]")) {
      refreshPinStatus();
    }
  });

  refreshPinStatus();
})();
