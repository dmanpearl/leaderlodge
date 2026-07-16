(function () {
  const modalEl = document.getElementById("location-show-place-modal");
  if (!modalEl || !window.LeaderLodgeLocationMap) return;

  const { LocationMapPicker } = window.LeaderLodgeLocationMap;

  const titleEl = document.getElementById("location-show-place-modal-label");
  const subtitleEl = document.getElementById("location-show-place-subtitle");
  const mapCanvas = document.getElementById("location-show-place-canvas");
  const statusEl = document.getElementById("location-show-place-status");

  const apiKey = modalEl.dataset.apiKey || "";
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

  let picker = null;

  function setStatus(message) {
    statusEl.textContent = message || "";
  }

  function resetModal() {
    setStatus("");
    if (picker) {
      picker.destroy();
      picker = null;
    }
    mapCanvas.innerHTML = "";
  }

  async function openShowPlace(context) {
    if (!apiKey) return;
    const name = context.locationName || "Location";
    const city = context.city || "";
    const state = context.state || "";
    titleEl.textContent = name;
    if (city && state) {
      subtitleEl.textContent = `${city}, ${state}`;
    } else if (city || state) {
      subtitleEl.textContent = city || state;
    } else {
      subtitleEl.textContent = "Pinned location";
    }

    const lat =
      context.lat != null && context.lat !== "" ? Number(context.lat) : null;
    const lon =
      context.lon != null && context.lon !== "" ? Number(context.lon) : null;
    if (lat == null || lon == null) {
      return;
    }

    modal.show();
    resetModal();
    picker = new LocationMapPicker(mapCanvas, {
      apiKey,
      readOnly: true,
      onStatus: setStatus,
    });
    try {
      await picker.init({ lat, lon });
    } catch (err) {
      setStatus(err?.message || "Could not load map.");
    }
  }

  modalEl.addEventListener("hidden.bs.modal", resetModal);

  modalEl.addEventListener("shown.bs.modal", () => {
    if (picker?.map) {
      google.maps.event.trigger(picker.map, "resize");
      const pos = picker.marker?.getPosition();
      if (pos) {
        picker.map.panTo(pos);
      }
    }
  });

  document.querySelectorAll("[data-location-show-place]").forEach((btn) => {
    btn.addEventListener("click", () => {
      openShowPlace({
        locationName: btn.dataset.locationName,
        city: btn.dataset.city,
        state: btn.dataset.state,
        lat: btn.dataset.lat,
        lon: btn.dataset.lon,
      });
    });
  });

  window.LeaderLodgeShowPlace = { open: openShowPlace };
})();
