/**
 * Smart Suggest: ranked player and team picks from recent game history.
 */
(function () {
  function playersAlreadyInGame(tbody) {
    const ids = new Set();
    if (!tbody) {
      return ids;
    }
    tbody.querySelectorAll("[data-game-row]").forEach((row) => {
      const primaryHidden = row.querySelector('[name="participant_player_id"]');
      const primaryValue = primaryHidden ? primaryHidden.value.trim() : "";
      if (primaryValue) {
        ids.add(Number(primaryValue));
      }
      const teammateHidden = row.querySelector(
        '[name="participant_teammate_player_id"]'
      );
      const teammateValue = teammateHidden ? teammateHidden.value.trim() : "";
      if (teammateValue) {
        ids.add(Number(teammateValue));
      }
    });
    return ids;
  }

  function gameTypeCode(form) {
    const select = form.querySelector('[name="game_type_code"]');
    if (select && select.value) {
      return select.value;
    }
    const hidden = form.querySelector('input[name="game_type_code"]');
    if (hidden && hidden.value.trim()) {
      return hidden.value.trim();
    }
    return (form.dataset.suggestGameTypeCode || "").trim();
  }

  function groupId(form) {
    const select = form.querySelector('[name="group"]');
    if (select && select.value) {
      return select.value;
    }
    const hidden = form.querySelector('input[name="group"]');
    if (hidden && hidden.value.trim()) {
      return hidden.value.trim();
    }
    return (form.dataset.suggestGroupId || "").trim();
  }

  function canAddSide(form, tbody) {
    if (!form || !tbody) {
      return false;
    }
    const max = Number.parseInt(form.dataset.maxPlayers, 10);
    if (Number.isNaN(max)) {
      return true;
    }
    return tbody.querySelectorAll("[data-game-row]").length < max;
  }

  function rosterEntryForPlayer(roster, player) {
    if (!player || !player.player_id) {
      return null;
    }
    return roster.find((entry) => String(entry.id) === String(player.player_id)) || null;
  }

  function applySuggestion(suggestion, picker, roster) {
    if (!suggestion || !Array.isArray(suggestion.players) || !picker) {
      return false;
    }
    if (suggestion.kind === "team" && suggestion.players.length > 1) {
      return window.LeaderLodgeRecordGame.appendSide({
        players: suggestion.players,
      });
    }
    const player = suggestion.players[0];
    const entry = rosterEntryForPlayer(roster, player);
    if (entry) {
      picker.addParticipant({ entry });
      return true;
    }
    if (player.player_id) {
      picker.addParticipant({
        entry: {
          id: player.player_id,
          label: player.label,
          kind: "member",
          username: null,
        },
      });
      return true;
    }
    picker.addParticipant({ guestName: player.guest_name || player.label });
    return true;
  }

  function renderSuggestions(menu, suggestions, picker, roster) {
    menu.innerHTML = "";
    if (!suggestions.length) {
      const empty = document.createElement("li");
      empty.className = "dropdown-item-text text-muted small";
      empty.textContent = "No recent players to suggest.";
      menu.appendChild(empty);
      return;
    }
    suggestions.forEach((suggestion) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "dropdown-item smart-suggest-option";
      button.dataset.kind = suggestion.kind || "solo";
      const badge =
        suggestion.kind === "team"
          ? '<span class="badge text-bg-primary ms-1">Team</span>'
          : "";
      button.innerHTML = `<span>${suggestion.label}</span>${badge}`;
      button.addEventListener("click", () => {
        applySuggestion(suggestion, picker, roster);
      });
      item.appendChild(button);
      menu.appendChild(item);
    });
  }

  async function loadSuggestions(form, menu, button) {
    const url = form.dataset.suggestSidesUrl;
    const group = groupId(form);
    const gameType = gameTypeCode(form);
    if (!url || !group || !gameType) {
      renderSuggestions(menu, [], null, []);
      button.disabled = true;
      return;
    }
    const tbody = form.querySelector("[data-participant-rows]");
    if (!canAddSide(form, tbody)) {
      renderSuggestions(menu, [], null, []);
      button.disabled = true;
      return;
    }
    button.disabled = false;
    const exclude = Array.from(playersAlreadyInGame(tbody)).join(",");
    const params = new URLSearchParams({
      group,
      type: gameType,
    });
    if (exclude) {
      params.set("exclude", exclude);
    }
    menu.innerHTML =
      '<li class="dropdown-item-text text-muted small">Loading…</li>';
    try {
      const response = await fetch(`${url}?${params.toString()}`, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error("request failed");
      }
      const payload = await response.json();
      const picker = window.LeaderLodgeRecordGame?.picker;
      let roster = [];
      try {
        const rosterEl = document.getElementById("game-roster-data");
        roster = rosterEl ? JSON.parse(rosterEl.textContent) : [];
      } catch (_error) {
        roster = [];
      }
      renderSuggestions(menu, payload.suggestions || [], picker, roster);
    } catch (_error) {
      menu.innerHTML =
        '<li class="dropdown-item-text text-muted small">Could not load suggestions.</li>';
    }
  }

  function initSmartSuggest() {
    const form =
      document.getElementById("game-record-form") ||
      document.getElementById("game-edit-form");
    if (!form || !form.dataset.suggestSidesUrl) {
      return;
    }
    const button = form.querySelector("[data-smart-suggest]");
    const menu = form.querySelector("[data-smart-suggest-menu]");
    if (!button || !menu) {
      return;
    }

    button.addEventListener("show.bs.dropdown", () => {
      window.LeaderLodgeRecordGame?.picker?.close?.();
      window.LeaderLodgeRecordGame?.teammatePicker?.close?.();
      loadSuggestions(form, menu, button);
    });

    const refreshState = () => {
      const tbody = form.querySelector("[data-participant-rows]");
      button.disabled = !canAddSide(form, tbody) || !groupId(form) || !gameTypeCode(form);
    };
    refreshState();
    form.addEventListener("change", refreshState);
    const tbody = form.querySelector("[data-participant-rows]");
    if (tbody) {
      const observer = new MutationObserver(refreshState);
      observer.observe(tbody, { childList: true, subtree: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSmartSuggest);
  } else {
    initSmartSuggest();
  }
})();
