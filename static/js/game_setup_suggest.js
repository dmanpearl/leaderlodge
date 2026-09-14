(function () {
  const form = document.getElementById("game-record-form");
  if (!form) {
    return;
  }

  const suggestUrl = form.dataset.suggestSidesUrl;
  const groupSelect = form.querySelector('[name="group"]');
  const gameSelect = form.querySelector('[name="game_type_code"]');
  const button = document.getElementById("suggest-sides-btn");
  const menu = document.getElementById("suggest-sides-menu");
  if (!suggestUrl || !groupSelect || !gameSelect || !button || !menu) {
    return;
  }

  let fetchTimer = null;
  let fetchId = 0;

  function clearSuggestAction() {
    button.disabled = true;
    menu.replaceChildren();
  }

  function hideSuggestMenu() {
    const dropdown = bootstrap.Dropdown.getInstance(button);
    if (dropdown) {
      dropdown.hide();
    }
  }

  function applyLineup(lineup) {
    const api = window.LeaderLodgeRecordGame;
    if (
      !api ||
      typeof api.clearParticipants !== "function" ||
      typeof api.appendSide !== "function" ||
      !lineup
    ) {
      return;
    }
    const sides = Array.isArray(lineup.sides) ? lineup.sides : [];
    if (!sides.length) {
      return;
    }

    api.clearParticipants();
    let added = 0;
    sides.forEach((side) => {
      const players = (side.players || [])
        .filter((player) => player && (player.player_id || player.guest_name))
        .map((player) => ({
          player_id: player.player_id,
          guest_name: player.guest_name || "",
          label: player.label || player.guest_name || "",
        }));
      if (players.length && api.appendSide({ players })) {
        added += 1;
      }
    });

    if (added > 0) {
      if (typeof api.collapsePlayerPicker === "function") {
        api.collapsePlayerPicker({ focusExpand: false });
      }
      hideSuggestMenu();
    }
  }

  function renderOptions(suggestions) {
    menu.replaceChildren();
    suggestions.forEach((lineup) => {
      const item = document.createElement("li");
      const choice = document.createElement("button");
      choice.type = "button";
      choice.className = "dropdown-item reuse-players-menu-item";
      choice.textContent = lineup.summary || "Lineup";
      choice.title = lineup.summary || "Lineup";
      choice.addEventListener("click", () => applyLineup(lineup));
      item.appendChild(choice);
      menu.appendChild(item);
    });
  }

  async function updateSuggestAction() {
    const groupId = groupSelect.value;
    const gameType = gameSelect.value;
    if (!groupId || !gameType) {
      clearSuggestAction();
      return;
    }

    const requestId = ++fetchId;
    try {
      const params = new URLSearchParams({
        group: groupId,
        game_type_code: gameType,
        lineup: "1",
      });
      const response = await fetch(`${suggestUrl}?${params.toString()}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok || requestId !== fetchId) {
        return;
      }
      const data = await response.json();
      if (requestId !== fetchId) {
        return;
      }
      const suggestions = Array.isArray(data.suggestions)
        ? data.suggestions
        : [];
      const available = suggestions.length > 0;
      button.disabled = !available;
      if (available) {
        renderOptions(suggestions);
      } else {
        menu.replaceChildren();
      }
    } catch (_error) {
      if (requestId === fetchId) {
        clearSuggestAction();
      }
    }
  }

  function scheduleUpdate() {
    clearSuggestAction();
    window.clearTimeout(fetchTimer);
    fetchTimer = window.setTimeout(updateSuggestAction, 150);
  }

  groupSelect.addEventListener("change", scheduleUpdate);
  gameSelect.addEventListener("change", scheduleUpdate);
  button.addEventListener("show.bs.dropdown", updateSuggestAction);
  updateSuggestAction();
})();
