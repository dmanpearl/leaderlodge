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

  function readRoster() {
    try {
      const rosterEl = document.getElementById("game-roster-data");
      return rosterEl ? JSON.parse(rosterEl.textContent) : [];
    } catch (_error) {
      return [];
    }
  }

  function rosterEntryForPlayer(roster, player) {
    if (!player || !player.player_id) {
      return null;
    }
    return (
      roster.find((entry) => String(entry.id) === String(player.player_id)) ||
      null
    );
  }

  function buildRowEntryFromPlayer(player) {
    const roster = readRoster();
    const entry = rosterEntryForPlayer(roster, player);
    if (entry) {
      return {
        id: entry.id,
        label: entry.label,
        username: entry.username,
        kind: entry.kind,
        guestName: "",
      };
    }
    if (player.player_id) {
      return {
        id: player.player_id,
        label: player.label,
        username: null,
        kind: "member",
        guestName: "",
      };
    }
    return {
      id: "",
      label: player.label || player.guest_name || "Guest",
      username: null,
      kind: "guest",
      guestName: player.guest_name || player.label || "",
    };
  }

  function applySuggestion(suggestion, context) {
    if (!suggestion || !Array.isArray(suggestion.players)) {
      return false;
    }
    const picker = window.LeaderLodgeRecordGame?.picker;
    const roster = readRoster();

    if (context.mode === "teammate" && context.row) {
      const player = suggestion.players[0];
      if (!player) {
        return false;
      }
      const teammatePicker = window.LeaderLodgeRecordGame?.teammatePicker;
      const teammateInput = context.row.querySelector("[data-add-teammate]");
      if (!teammatePicker || !teammateInput) {
        return false;
      }
      teammatePicker.activate(teammateInput);
      teammatePicker.assignFromEntry({
        entry: buildRowEntryFromPlayer(player),
      });
      document
        .querySelector("[data-smart-suggest-teammate-menu].show")
        ?.classList.remove("show");
      return true;
    }

    if (!picker) {
      return false;
    }
    picker.suppressBlurCommit = true;
    let applied = false;
    if (suggestion.kind === "team" && suggestion.players.length > 1) {
      applied = window.LeaderLodgeRecordGame.appendSide({
        players: suggestion.players,
      });
    } else {
      const player = suggestion.players[0];
      const entry = rosterEntryForPlayer(roster, player);
      if (entry) {
        picker.addParticipant({ entry });
        applied = true;
      } else {
        picker.addParticipant({ entry: buildRowEntryFromPlayer(player) });
        applied = true;
      }
    }
    if (applied && picker.input) {
      picker.skipRefresh = true;
      picker.input.value = "";
      picker.close();
    }
    return applied;
  }

  function closeSmartSuggestMenus(menu) {
    if (menu) {
      menu.classList.remove("show");
      const toggle = menu
        .closest(".dropdown")
        ?.querySelector("[data-bs-toggle='dropdown']");
      if (toggle && window.bootstrap?.Dropdown) {
        window.bootstrap.Dropdown.getInstance(toggle)?.hide();
      }
    }
    document
      .querySelector("[data-smart-suggest-teammate-menu].show")
      ?.classList.remove("show");
  }

  function renderSuggestions(menu, suggestions, context) {
    menu.innerHTML = "";
    if (!suggestions.length) {
      const empty = document.createElement("li");
      empty.className = "dropdown-item-text text-muted small";
      empty.textContent = context.query
        ? "No matching recent players."
        : "No recent players to suggest.";
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
      button.addEventListener("mousedown", (event) => {
        event.preventDefault();
      });
      button.addEventListener("click", () => {
        applySuggestion(suggestion, context);
        closeSmartSuggestMenus(menu);
      });
      item.appendChild(button);
      menu.appendChild(item);
    });
  }

  function queryForContext(form, context) {
    if (context.mode === "teammate" && context.row) {
      const teammateInput = context.row.querySelector("[data-add-teammate]");
      return teammateInput ? teammateInput.value.trim() : "";
    }
    const playerInput = form.querySelector("[data-player-picker]");
    return playerInput ? playerInput.value.trim() : "";
  }

  async function loadSuggestions(form, menu, button, context) {
    const url = form.dataset.suggestSidesUrl;
    const group = groupId(form);
    const gameType = gameTypeCode(form);
    if (!context.queryCaptured) {
      context.query = queryForContext(form, context);
    }
    const query = context.query || "";

    if (!url || !group || !gameType) {
      renderSuggestions(menu, [], context);
      button.disabled = true;
      return;
    }

    const tbody = form.querySelector("[data-participant-rows]");
    if (context.mode === "side" && !canAddSide(form, tbody)) {
      renderSuggestions(menu, [], context);
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
    if (query) {
      params.set("q", query);
    }
    if (context.mode === "teammate") {
      params.set("mode", "teammate");
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
      renderSuggestions(menu, payload.suggestions || [], context);
    } catch (_error) {
      menu.innerHTML =
        '<li class="dropdown-item-text text-muted small">Could not load suggestions.</li>';
    }
  }

  function suppressPickerBlurCommit() {
    const picker = window.LeaderLodgeRecordGame?.picker;
    if (picker) {
      picker.suppressBlurCommit = true;
    }
    const teammatePicker = window.LeaderLodgeRecordGame?.teammatePicker;
    if (teammatePicker) {
      teammatePicker.skipRefresh = true;
    }
  }

  function initSmartSuggest() {
    const form =
      document.getElementById("game-record-form") ||
      document.getElementById("game-edit-form");
    if (!form || !form.dataset.suggestSidesUrl) {
      return;
    }

    const sideButton = form.querySelector("[data-smart-suggest]");
    const sideMenu = form.querySelector("[data-smart-suggest-menu]");
    const sideContext = {
      mode: "side",
      row: null,
      query: "",
      queryCaptured: false,
    };

    if (sideButton && sideMenu) {
      const captureSideQuery = () => {
        suppressPickerBlurCommit();
        sideContext.query = queryForContext(form, sideContext);
        sideContext.queryCaptured = true;
      };
      sideButton.addEventListener("pointerdown", captureSideQuery, true);
      sideButton.addEventListener("mousedown", captureSideQuery);
      sideButton.addEventListener("touchstart", captureSideQuery, {
        passive: true,
      });
      sideButton.addEventListener("show.bs.dropdown", () => {
        if (!sideContext.queryCaptured) {
          captureSideQuery();
        }
        window.LeaderLodgeRecordGame?.teammatePicker?.close?.();
        loadSuggestions(form, sideMenu, sideButton, sideContext);
      });
      sideButton.addEventListener("hidden.bs.dropdown", () => {
        sideContext.queryCaptured = false;
        sideContext.query = "";
      });

      const refreshState = () => {
        const tbody = form.querySelector("[data-participant-rows]");
        sideButton.disabled =
          !canAddSide(form, tbody) || !groupId(form) || !gameTypeCode(form);
      };
      refreshState();
      form.addEventListener("change", refreshState);
      const tbody = form.querySelector("[data-participant-rows]");
      if (tbody) {
        const observer = new MutationObserver(refreshState);
        observer.observe(tbody, { childList: true, subtree: true });
      }
    }

    let teammateMenu = null;
    let teammateToggle = null;

    function ensureTeammateMenu() {
      if (teammateMenu) {
        return teammateMenu;
      }
      teammateMenu = document.createElement("ul");
      teammateMenu.className =
        "dropdown-menu dropdown-menu-end smart-suggest-menu smart-suggest-menu--teammate";
      teammateMenu.dataset.smartSuggestTeammateMenu = "1";
      teammateMenu.setAttribute("data-smart-suggest-teammate-menu", "");
      document.body.appendChild(teammateMenu);
      return teammateMenu;
    }

    window.LeaderLodgeSmartSuggest = {
      openForTeammate(row) {
        if (!row) {
          return;
        }
        const menu = ensureTeammateMenu();
        const teammateInput = row.querySelector("[data-add-teammate]");
        const context = {
          mode: "teammate",
          row,
          query: teammateInput ? teammateInput.value.trim() : "",
          queryCaptured: true,
        };
        if (teammateInput) {
          window.LeaderLodgeRecordGame?.teammatePicker?.activate?.(
            teammateInput
          );
        }
        loadSuggestions(form, menu, { disabled: false }, context).then(() => {
          if (!teammateInput) {
            return;
          }
          const rect = teammateInput.getBoundingClientRect();
          menu.classList.add("show");
          menu.style.position = "fixed";
          menu.style.left = `${Math.max(8, rect.left)}px`;
          menu.style.top = `${rect.bottom}px`;
          menu.style.minWidth = `${Math.max(rect.width, 160)}px`;
          menu.style.zIndex = "1090";

          const closeMenu = (event) => {
            if (
              event.target instanceof Node &&
              (menu.contains(event.target) ||
                teammateInput.contains(event.target))
            ) {
              return;
            }
            menu.classList.remove("show");
            document.removeEventListener("pointerdown", closeMenu, true);
          };
          document.addEventListener("pointerdown", closeMenu, true);
        });
      },
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSmartSuggest);
  } else {
    initSmartSuggest();
  }
})();
