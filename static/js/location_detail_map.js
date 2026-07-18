(function () {
  const canvas = document.getElementById("location-detail-map-canvas");
  if (!canvas || !window.LeaderLodgeLocationMap) return;

  const { LocationMapPicker } = window.LeaderLodgeLocationMap;
  const statusEl = document.getElementById("location-detail-map-status");
  const apiKey = canvas.dataset.apiKey || "";
  const lat = canvas.dataset.lat ? Number(canvas.dataset.lat) : null;
  const lon = canvas.dataset.lon ? Number(canvas.dataset.lon) : null;

  function setStatus(message, isError) {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.classList.toggle("text-danger", Boolean(isError));
    statusEl.classList.toggle("text-muted", !isError && Boolean(message));
  }

  if (!apiKey || lat == null || lon == null || Number.isNaN(lat) || Number.isNaN(lon)) {
    setStatus("Map unavailable for this location.", true);
    return;
  }

  const picker = new LocationMapPicker(canvas, {
    apiKey,
    readOnly: true,
    onStatus: setStatus,
  });

  picker
    .init({ lat, lon })
    .then(function () {
      setStatus("");
    })
    .catch(function (err) {
      setStatus(err?.message || "Could not load map.", true);
    });
})();
