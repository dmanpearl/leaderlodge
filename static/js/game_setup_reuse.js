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
  const menu = document.getElementById("reuse-players-menu");
  const reuseGameIdInput = document.getElementById("reuse-game-id");
  if (
    !previewUrl ||
    !groupSelect ||
    !gameSelect ||
    !button ||
    !menu ||
    !reuseGameIdInput
  ) {
    return;
  }

  let fetchTimer = null;
  let fetchId = 0;

  function clearReuseAction() {
    button.disabled = true;
    menu.replaceChildren();
    reuseGameIdInput.value = "";
  }

  function submitReuse(gameId) {
    reuseGameIdInput.value = String(gameId);
    const actionInput = document.createElement("input");
    actionInput.type = "hidden";
    actionInput.name = "action";
    actionInput.value = "reuse_roster";
    form.appendChild(actionInput);
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit();
    } else {
      form.submit();
    }
  }

  function renderOptions(options) {
    menu.replaceChildren();
    options.forEach((option) => {
      const item = document.createElement("li");
      const choice = document.createElement("button");
      choice.type = "button";
      choice.className = "dropdown-item reuse-players-menu-item";
      choice.textContent = option.summary;
      choice.title = option.summary;
      choice.addEventListener("click", () => submitReuse(option.game_id));
      item.appendChild(choice);
      menu.appendChild(item);
    });
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
      const options = Array.isArray(data.options) ? data.options : [];
      const available = Boolean(data.available) && options.length > 0;
      button.disabled = !available;
      if (available) {
        renderOptions(options);
      } else {
        menu.replaceChildren();
      }
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
