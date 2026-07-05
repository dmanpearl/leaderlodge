(function () {
  const form = document.getElementById("game-setup-form");
  if (!form) {
    return;
  }

  const previewUrl = form.dataset.reusePreviewUrl;
  const groupSelect = form.querySelector('[name="group"]');
  const gameSelect = form.querySelector('[name="game_type_code"]');
  const locationInput = form.querySelector('[name="location_name"]');
  const button = document.getElementById("reuse-players-btn");
  const summary = document.getElementById("reuse-players-summary");
  if (!previewUrl || !groupSelect || !gameSelect || !button || !summary) {
    return;
  }

  let fetchTimer = null;
  let fetchId = 0;

  function clearReuseAction() {
    button.disabled = true;
    summary.textContent = "";
  }

  async function updateReuseAction() {
    const groupId = groupSelect.value;
    const gameType = gameSelect.value;
    if (!groupId || !gameType) {
      clearReuseAction();
      return;
    }

    const requestId = ++fetchId;
    try {
      const params = new URLSearchParams({
        group: groupId,
        game_type_code: gameType,
      });
      const response = await fetch(`${previewUrl}?${params.toString()}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok || requestId !== fetchId) {
        return;
      }
      const data = await response.json();
      if (requestId !== fetchId) {
        return;
      }
      button.disabled = !data.available;
      summary.textContent = data.available ? data.summary : "";
      if (locationInput) {
        locationInput.value = data.last_location_name || "";
        locationInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
    } catch (_error) {
      if (requestId === fetchId) {
        clearReuseAction();
      }
    }
  }

  function scheduleUpdate() {
    clearReuseAction();
    window.clearTimeout(fetchTimer);
    fetchTimer = window.setTimeout(updateReuseAction, 150);
  }

  groupSelect.addEventListener("change", scheduleUpdate);
  gameSelect.addEventListener("change", scheduleUpdate);
  updateReuseAction();
})();
