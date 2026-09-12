/**
 * Fuzzy player picker for game recording: roster members and guests.
 */
(function () {
  const MAX_SUGGESTIONS = 8;

  function foldAccents(value) {
    return value.normalize("NFD").replace(/\p{M}/gu, "");
  }

  function normalizeForMatch(value) {
    const folded = foldAccents(value.trim().toLowerCase());
    return folded.replace(/[^a-z0-9\s']/g, "");
  }

  // Browsers (especially iOS Safari) ignore autocomplete=off for name-like
  // fields. Use a non-semantic token plus readonly-until-interaction.
  function suppressBrowserSuggestions(input) {
    input.setAttribute("autocomplete", "ll-player");
    input.setAttribute("autocorrect", "off");
    input.setAttribute("autocapitalize", "off");
    input.setAttribute("spellcheck", "false");
    if (!input.hasAttribute("readonly")) {
      input.setAttribute("readonly", "readonly");
    }
    const unlock = () => {
      if (input.hasAttribute("readonly")) {
        input.removeAttribute("readonly");
      }
    };
    input.addEventListener("focus", unlock);
    input.addEventListener("touchstart", unlock, { passive: true });
    // Autofocus may run before this script; unlock if already focused.
    if (document.activeElement === input) {
      unlock();
    }
  }

  function scoreMatch(query, candidate) {
    const q = normalizeForMatch(query);
    const n = normalizeForMatch(candidate);
    if (!q) {
      return -1;
    }
    if (n === q) {
      return 200;
    }
    if (n.startsWith(q)) {
      return 100 - (n.length - q.length);
    }
    if (n.includes(q)) {
      return 50 - (n.length - q.length);
    }

    let queryIndex = 0;
    for (let i = 0; i < n.length && queryIndex < q.length; i += 1) {
      if (n[i] === q[queryIndex]) {
        queryIndex += 1;
      }
    }
    if (queryIndex === q.length) {
      return 10;
    }
    return -1;
  }

  function filterRoster(roster, query) {
    if (!query.trim()) {
      return [];
    }

    return roster
      .map((entry) => {
        let bestScore = scoreMatch(query, entry.label);
        if (entry.username) {
          bestScore = Math.max(bestScore, scoreMatch(query, entry.username));
        }
        if (entry.kind === "team" && Array.isArray(entry.members)) {
          entry.members.forEach((member) => {
            bestScore = Math.max(bestScore, scoreMatch(query, member.label));
            if (member.username) {
              bestScore = Math.max(bestScore, scoreMatch(query, member.username));
            }
          });
        }
        return { entry, score: bestScore };
      })
      .filter((item) => item.score >= 0)
      .sort((a, b) => {
        // Teams never used for the current game type sort after everything
        // else (including lower-scoring individual matches), so a team's
        // recency in an unrelated game type cannot win it a top slot.
        const aTier = a.entry.deprioritized ? 1 : 0;
        const bTier = b.entry.deprioritized ? 1 : 0;
        if (aTier !== bTier) {
          return aTier - bTier;
        }
        if (b.score !== a.score) {
          return b.score - a.score;
        }
        const aRecency = a.entry.recency ?? Number.MAX_SAFE_INTEGER;
        const bRecency = b.entry.recency ?? Number.MAX_SAFE_INTEGER;
        if (aRecency !== bRecency) {
          return aRecency - bRecency;
        }
        return a.entry.label.localeCompare(b.entry.label);
      })
      .slice(0, MAX_SUGGESTIONS)
      .map((item) => item.entry);
  }

  function readSmartSuggestions() {
    try {
      const el = document.getElementById("game-smart-suggestions-data");
      return el ? JSON.parse(el.textContent) : [];
    } catch (_error) {
      return [];
    }
  }

  function smartPlayerIds(suggestion) {
    return (suggestion?.players || [])
      .map((player) => Number(player.player_id))
      .filter((id) => !Number.isNaN(id) && id > 0);
  }

  function rosterEntryFromSmartPlayer(roster, player) {
    if (!player) {
      return null;
    }
    if (player.player_id) {
      const entry = roster.find(
        (item) => String(item.id) === String(player.player_id)
      );
      if (entry) {
        return entry;
      }
      return {
        id: player.player_id,
        label: player.label,
        username: null,
        kind: "member",
        guestName: "",
      };
    }
    const guestName = player.guest_name || player.label || "";
    return {
      id: "",
      label: guestName || "Guest",
      username: null,
      kind: "guest",
      guestName,
    };
  }

  function smartSuggestionMatchesQuery(suggestion, query) {
    const trimmed = query.trim();
    if (!trimmed) {
      return true;
    }
    if (scoreMatch(trimmed, suggestion.label || "") >= 0) {
      return true;
    }
    return (suggestion.players || []).some(
      (player) => scoreMatch(trimmed, player.label || "") >= 0
    );
  }

  function filterSmartSuggestionsForPlayer(smartList, tbody) {
    const inGame = playersAlreadyInGame(tbody);
    return smartList.filter((suggestion) => {
      const ids = smartPlayerIds(suggestion);
      return ids.length > 0 && !ids.some((id) => inGame.has(id));
    });
  }

  function filterSmartSuggestionsForTeammate(smartList, tbody, row, roster) {
    return smartList.filter((suggestion) => {
      if (suggestion.kind !== "solo") {
        return false;
      }
      const entry = rosterEntryFromSmartPlayer(roster, suggestion.players?.[0]);
      if (!entry) {
        return false;
      }
      return !entryIsIneligibleForTeammate(tbody, row, entry, roster);
    });
  }

  function comboboxOptionHtml(item) {
    if (item.type === "guest") {
      return `Add guest "${item.entry.guestName}"`;
    }
    if (item.type === "smart-team") {
      return `<span>${item.label}</span> <span class="badge text-bg-primary ms-1">Team</span> <span class="badge text-bg-secondary ms-1">Recent</span>`;
    }
    const entry = item.entry;
    const detail =
      entry?.kind === "team"
        ? "team"
        : entry?.username
          ? entry.username
          : entry?.kind === "guest"
            ? "guest"
            : "";
    const recentBadge =
      item.type === "smart-solo"
        ? ' <span class="badge text-bg-secondary ms-1">Recent</span>'
        : "";
    return `<span>${entry?.label || item.label}</span>${
      detail ? ` <span class="text-muted small">${detail}</span>` : ""
    }${recentBadge}`;
  }

  function labelsMatch(a, b) {
    return normalizeForMatch(a) === normalizeForMatch(b);
  }

  function rowKeyForEntry(entry) {
    if (entry.id) {
      return `player-${entry.id}`;
    }
    return `guest-${normalizeForMatch(entry.guestName)}`;
  }

  function existingRowKeys(tbody) {
    const keys = new Set();
    tbody.querySelectorAll("[data-game-row]").forEach((row) => {
      if (row.dataset.rowKey) {
        keys.add(row.dataset.rowKey);
      }
      if (row.dataset.teammateKey) {
        keys.add(row.dataset.teammateKey);
      }
    });
    return keys;
  }

  function playerIdsForRow(row) {
    const ids = new Set();
    if (!row) {
      return ids;
    }
    const primaryHidden = row.querySelector('[name="participant_player_id"]');
    const primaryValue = primaryHidden ? primaryHidden.value.trim() : "";
    if (primaryValue) {
      ids.add(Number(primaryValue));
    } else {
      const primaryId = row.dataset.playerId;
      if (primaryId && !String(primaryId).startsWith("guest:")) {
        ids.add(Number(primaryId));
      }
    }
    const teammateHidden = row.querySelector(
      '[name="participant_teammate_player_id"]'
    );
    const teammateValue = teammateHidden ? teammateHidden.value.trim() : "";
    if (teammateValue) {
      ids.add(Number(teammateValue));
    }
    return ids;
  }

  function playersAlreadyInGame(tbody) {
    const ids = new Set();
    if (!tbody) {
      return ids;
    }
    tbody.querySelectorAll("[data-game-row]").forEach((row) => {
      playerIdsForRow(row).forEach((playerId) => ids.add(playerId));
    });
    return ids;
  }

  function playersOnOtherSides(tbody, currentRow) {
    const ids = new Set();
    if (!tbody) {
      return ids;
    }
    tbody.querySelectorAll("[data-game-row]").forEach((row) => {
      if (row === currentRow) {
        return;
      }
      playerIdsForRow(row).forEach((playerId) => ids.add(playerId));
    });
    return ids;
  }

  function memberIdsForRosterEntry(entry, roster) {
    if (Array.isArray(entry.members) && entry.members.length > 0) {
      return entry.members
        .map((member) => Number(member.id))
        .filter((id) => !Number.isNaN(id));
    }

    if (entry.kind === "team" && Array.isArray(roster)) {
      const fullEntry = roster.find(
        (candidate) => candidate.id === entry.id && candidate.kind === "team"
      );
      if (Array.isArray(fullEntry?.members) && fullEntry.members.length > 0) {
        return fullEntry.members
          .map((member) => Number(member.id))
          .filter((id) => !Number.isNaN(id));
      }
    }

    if (entry.id) {
      const id = Number(entry.id);
      return Number.isNaN(id) ? [] : [id];
    }
    return [];
  }

  function entrySharesPlayerWithGame(tbody, entry, roster) {
    const playerIds = playersAlreadyInGame(tbody);
    if (playerIds.size === 0) {
      return false;
    }
    return memberIdsForRosterEntry(entry, roster).some((id) => playerIds.has(id));
  }

  function teamSideAlreadyAdded(tbody, entry) {
    if (!entry.members || entry.members.length < 2) {
      return false;
    }
    const memberIds = new Set(
      memberIdsForRosterEntry(entry, []).map((id) => Number(id))
    );
    return Array.from(tbody.querySelectorAll("[data-game-row]")).some((row) => {
      const rowMemberIds = new Set();
      const primaryHidden = row.querySelector('[name="participant_player_id"]');
      const primaryValue = primaryHidden ? primaryHidden.value.trim() : "";
      if (primaryValue) {
        rowMemberIds.add(Number(primaryValue));
      } else {
        const primaryId = row.dataset.playerId;
        if (primaryId && !primaryId.startsWith("guest:")) {
          rowMemberIds.add(Number(primaryId));
        }
      }
      const teammateHidden = row.querySelector(
        '[name="participant_teammate_player_id"]'
      );
      const teammateValue = teammateHidden ? teammateHidden.value.trim() : "";
      if (teammateValue) {
        rowMemberIds.add(Number(teammateValue));
      }
      if (rowMemberIds.size !== memberIds.size) {
        return false;
      }
      for (const memberId of memberIds) {
        if (!rowMemberIds.has(memberId)) {
          return false;
        }
      }
      return true;
    });
  }

  function entryIsIneligible(tbody, entry, existing, roster) {
    if (entry.kind === "team" && teamSideAlreadyAdded(tbody, entry)) {
      return true;
    }
    if (entry.id && existing.has(rowKeyForEntry({ id: entry.id }))) {
      return true;
    }
    return entrySharesPlayerWithGame(tbody, entry, roster);
  }

  function entryIsIneligibleForTeammate(tbody, row, entry, roster) {
    if (entry.kind === "team") {
      return true;
    }
    const memberIds = memberIdsForRosterEntry(entry, roster);
    if (!memberIds.length) {
      return true;
    }
    const rowIds = playerIdsForRow(row);
    if (memberIds.some((memberId) => rowIds.has(memberId))) {
      return true;
    }
    const blockedIds = playersOnOtherSides(tbody, row);
    return memberIds.some((memberId) => blockedIds.has(memberId));
  }

  function rosterEntryMatchesLabel(entry, label) {
    if (labelsMatch(entry.label, label)) {
      return true;
    }
    if (entry.username && labelsMatch(entry.username, label)) {
      return true;
    }
    if (entry.kind === "team" && Array.isArray(entry.members)) {
      return entry.members.some(
        (member) =>
          labelsMatch(member.label, label) ||
          (member.username && labelsMatch(member.username, label))
      );
    }
    return false;
  }

  function buildRowEntry({ entry, guestName }) {
    if (entry) {
      return {
        id: entry.id,
        label: entry.label,
        username: entry.username,
        kind: entry.kind,
        guestName: "",
      };
    }
    return {
      id: "",
      label: guestName,
      username: null,
      kind: "guest",
      guestName,
    };
  }

  function detailBadge(rowEntry) {
    const detail =
      rowEntry.username ||
      (rowEntry.id && rowEntry.kind === "guest"
        ? "Guest"
        : rowEntry.id
          ? ""
          : "New guest");
    return detail === "Guest" || detail === "New guest"
      ? `<span class="badge text-bg-secondary">${detail}</span>`
      : detail
        ? `(${detail})`
        : "";
  }

  function getRecordForm(tbody) {
    return tbody
      ? tbody.closest("#game-record-form, #game-edit-form")
      : null;
  }

  function isEditForm(form) {
    return form?.id === "game-edit-form";
  }

  function getSideLimits(form) {
    if (!form) {
      return { min: 0, max: Number.MAX_SAFE_INTEGER };
    }
    const min = Number.parseInt(form.dataset.minPlayers, 10);
    const max = Number.parseInt(form.dataset.maxPlayers, 10);
    return {
      min: Number.isNaN(min) ? 0 : min,
      max: Number.isNaN(max) ? Number.MAX_SAFE_INTEGER : max,
    };
  }

  function countSides(tbody) {
    if (!tbody) {
      return 0;
    }
    return tbody.querySelectorAll("[data-game-row]").length;
  }

  function canAddSide(form, tbody) {
    const { max } = getSideLimits(form);
    return countSides(tbody) < max;
  }

  function rowControlsHtml() {
    return `
              <div class="dropdown d-none" data-side-menu-wrap>
                <button
                  type="button"
                  class="btn btn-sm btn-outline-secondary"
                  data-bs-toggle="dropdown"
                  aria-expanded="false"
                  aria-label="Side options"
                >
                  <i class="bi bi-three-dots" aria-hidden="true"></i>
                </button>
                <ul class="dropdown-menu dropdown-menu-end" data-side-menu></ul>
              </div>
              <button
                type="button"
                class="btn btn-sm btn-outline-danger d-none"
                data-remove-side
                aria-label="Remove side"
                title="Remove side"
              >
                <i class="bi bi-trash" aria-hidden="true"></i>
              </button>
    `;
  }

  function initRowMenuDropdown(row) {
    const toggle = row.querySelector(
      "[data-side-menu-wrap] [data-bs-toggle='dropdown']"
    );
    if (!toggle || toggle.dataset.rowMenuReady === "1") {
      return;
    }
    toggle.dataset.rowMenuReady = "1";
    if (window.bootstrap?.Dropdown) {
      new window.bootstrap.Dropdown(toggle, {
        popperConfig: (defaultConfig) => ({
          ...defaultConfig,
          strategy: "fixed",
        }),
      });
    }
  }

  function buildSideActions(row) {
    const actions = [{ action: "remove-side", label: "Remove side" }];
    const hasTeammate = Boolean(row.dataset.teammateLabel);
    if (hasTeammate) {
      const primaryLabel = row.dataset.primaryLabel || "player";
      const teammateLabel = row.dataset.teammateLabel || "";
      actions.push({
        action: "remove-teammate",
        label: `Remove ${teammateLabel}`,
      });
      actions.push({
        action: "remove-primary",
        label: `Remove ${primaryLabel}`,
      });
    }
    return actions;
  }

  function appendSideActionMenuItem(menu, action, label) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "dropdown-item d-flex align-items-center gap-2";
    button.dataset.sideAction = action;
    const icon = document.createElement("i");
    icon.className = "bi bi-trash side-action-trash";
    icon.setAttribute("aria-hidden", "true");
    const text = document.createElement("span");
    text.textContent = label;
    button.appendChild(icon);
    button.appendChild(text);
    item.appendChild(button);
    menu.appendChild(item);
  }

  function updateSideActions(row) {
    const menuWrap = row.querySelector("[data-side-menu-wrap]");
    const menu = row.querySelector("[data-side-menu]");
    const soloRemoveBtn = row.querySelector("[data-remove-side]");
    if (!menuWrap || !menu) {
      return;
    }

    const actions = buildSideActions(row);
    if (actions.length === 1) {
      menuWrap.classList.add("d-none");
      menu.replaceChildren();
      if (soloRemoveBtn) {
        soloRemoveBtn.classList.remove("d-none");
      }
      return;
    }

    if (soloRemoveBtn) {
      soloRemoveBtn.classList.add("d-none");
    }
    menuWrap.classList.remove("d-none");
    menu.replaceChildren();
    actions.forEach(({ action, label }) => {
      appendSideActionMenuItem(menu, action, label);
    });
    initRowMenuDropdown(row);
  }

  function refreshSideLimitsUI(form, tbody) {
    if (!form || !tbody) {
      return;
    }
    tbody.querySelectorAll("[data-game-row]").forEach((row) => {
      updateSideLabel(row, form, tbody);
    });
    const expandBtn = form.querySelector("[data-player-picker-expand]");
    if (expandBtn) {
      expandBtn.disabled = !canAddSide(form, tbody);
    }
    if (window.LeaderLodgeUpdateGameRecordForm) {
      window.LeaderLodgeUpdateGameRecordForm();
    }
  }

  function sideLabel(primaryLabel, teammateLabel) {
    if (!teammateLabel) {
      return primaryLabel;
    }
    return [primaryLabel, teammateLabel]
      .sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))
      .join("+");
  }

  function resolvePrimaryLabel(row, labelEl) {
    let primaryLabel =
      row.dataset.primaryLabel || labelEl?.dataset.primaryLabel || "";
    if (primaryLabel) {
      return primaryLabel;
    }
    const guestName = row
      .querySelector('[name="participant_guest_name"]')
      ?.value?.trim();
    if (guestName) {
      return guestName;
    }
    return "";
  }

  function updateSideLabel(row, form, tbody) {
    const labelEl = row.querySelector("[data-side-label]");
    if (!labelEl) {
      return;
    }
    const body = tbody || row.closest("[data-participant-rows]");
    const gameForm = form || getRecordForm(body);
    let primaryLabel = resolvePrimaryLabel(row, labelEl);
    if (primaryLabel && !row.dataset.primaryLabel) {
      row.dataset.primaryLabel = primaryLabel;
      if (!row.dataset.primaryDetail) {
        row.dataset.primaryDetail = detailBadge(
          buildRowEntry({ guestName: primaryLabel })
        );
      }
    }
    const teammateLabel = row.dataset.teammateLabel || "";
    const hasTeammate = Boolean(teammateLabel);
    labelEl.innerHTML = `${sideLabel(primaryLabel, teammateLabel)}${
      hasTeammate
        ? ' <span class="badge text-bg-primary ms-1 participant-team-badge">Team</span>'
        : row.dataset.primaryDetail
          ? ` <span class="text-muted small ms-1">${row.dataset.primaryDetail}</span>`
          : ""
    }`;
    const addWrap = row.querySelector("[data-add-teammate-wrap]");
    if (addWrap) {
      addWrap.classList.toggle("d-none", hasTeammate);
    }
    row.dataset.hasTeammate = hasTeammate ? "1" : "";
    updateSideActions(row);
  }

  function appendParticipantRow(
    tbody,
    rowEntry,
    defaultParticipantScore,
    focusEl,
    form
  ) {
    const gameForm = form || getRecordForm(tbody);
    if (gameForm && !canAddSide(gameForm, tbody)) {
      return false;
    }
    const rowKey = rowKeyForEntry(
      rowEntry.id ? { id: rowEntry.id } : { guestName: rowEntry.guestName }
    );
    if (existingRowKeys(tbody).has(rowKey)) {
      return false;
    }
    if (rowEntry.id && playersAlreadyInGame(tbody).has(Number(rowEntry.id))) {
      return false;
    }

    const row = document.createElement("tr");
    row.setAttribute("data-game-row", "");
    row.dataset.rowKey = rowKey;
    row.dataset.playerId = rowEntry.id
      ? String(rowEntry.id)
      : `guest:${normalizeForMatch(rowEntry.guestName)}`;
    row.dataset.primaryLabel = rowEntry.label;
    row.dataset.primaryDetail = detailBadge(rowEntry);

    const initialScoreAttr = defaultParticipantScore
      ? ` data-initial-score="${defaultParticipantScore}"`
      : "";

    row.innerHTML = `
        <td>
          <div class="d-flex align-items-center justify-content-between gap-2 participant-label">
            <span data-side-label>
              ${rowEntry.label}
              ${
                row.dataset.primaryDetail
                  ? `<span class="text-muted small ms-1">${row.dataset.primaryDetail}</span>`
                  : ""
              }
            </span>
            <span class="d-flex align-items-center gap-1 flex-shrink-0">
              <div class="combobox-input-wrap" data-add-teammate-wrap>
                <input
                  type="text"
                  class="form-control form-control-sm game-record-teammate-input"
                  data-add-teammate
                  placeholder="Teammate"
                  aria-label="Teammate"
                  name="ll_teammate_search"
                  autocomplete="ll-player"
                  autocorrect="off"
                  autocapitalize="off"
                  spellcheck="false"
                  readonly
                />
              </div>
              ${rowControlsHtml()}
            </span>
          </div>
          <input type="hidden" name="participant_player_id" value="${rowEntry.id || ""}" />
          <input type="hidden" name="participant_guest_name" value="${rowEntry.guestName || ""}" />
          <input type="hidden" name="participant_teammate_player_id" value="" />
          <input type="hidden" name="participant_teammate_guest_name" value="" />
        </td>
        <td>
          <input
            type="text"
            inputmode="numeric"
            name="participant_score"
            class="form-control form-control-sm game-record-score-input"
            data-score-input${initialScoreAttr}
            value="${defaultParticipantScore}"
            autocomplete="off"
            autocorrect="off"
            autocapitalize="off"
            spellcheck="false"
            style="max-width: 6rem;"
          />
        </td>
        <td data-result-cell></td>
      `;

    tbody.appendChild(row);
    const teammateInput = row.querySelector("[data-add-teammate]");
    if (teammateInput) {
      window.LeaderLodgeRecordGame?.teammatePicker?.prepareInput?.(teammateInput);
    }
    updateSideLabel(row, gameForm, tbody);
    const scoreInput = row.querySelector("[data-score-input]");
    if (defaultParticipantScore !== "") {
      scoreInput.value = defaultParticipantScore;
    }
    if (focusEl) {
      focusEl.focus();
    }
    return true;
  }

  function appendTeamRow(tbody, entry, defaultParticipantScore, focusEl, form) {
    const gameForm = form || getRecordForm(tbody);
    if (gameForm && !canAddSide(gameForm, tbody)) {
      return false;
    }
    const members = entry.members;
    if (!members || members.length < 2) {
      return false;
    }
    if (teamSideAlreadyAdded(tbody, entry)) {
      return false;
    }
    if (entrySharesPlayerWithGame(tbody, entry, null)) {
      return false;
    }

    const primaryEntry = buildRowEntry({ entry: members[0] });
    const teammateEntry = buildRowEntry({ entry: members[1] });
    const added = appendParticipantRow(
      tbody,
      primaryEntry,
      defaultParticipantScore,
      null,
      gameForm
    );
    if (!added) {
      return false;
    }

    const row = tbody.querySelector(
      `[data-game-row][data-row-key="${rowKeyForEntry({ id: members[0].id })}"]`
    );
    if (!row) {
      return false;
    }
    assignTeammate(row, teammateEntry);
    if (focusEl) {
      focusEl.focus();
    }
    return true;
  }

  function teammateAssignmentAllowed(row, rowEntry, tbody) {
    const teammateKey = rowEntry.id
      ? `player-${rowEntry.id}`
      : `guest-${normalizeForMatch(rowEntry.guestName)}`;
    if (row.dataset.rowKey === teammateKey) {
      return false;
    }
    if (rowEntry.id && playersAlreadyInGame(tbody).has(Number(rowEntry.id))) {
      const primaryId = row.dataset.playerId;
      const onThisRow =
        (primaryId && Number(primaryId) === Number(rowEntry.id)) ||
        row.dataset.rowKey === teammateKey;
      if (!onThisRow) {
        return false;
      }
    }
    if (
      existingRowKeys(tbody).has(teammateKey) &&
      row.dataset.rowKey !== teammateKey
    ) {
      return !Array.from(tbody.querySelectorAll("[data-game-row]")).some(
        (other) =>
          other !== row &&
          (other.dataset.rowKey === teammateKey ||
            other.dataset.teammateKey === teammateKey)
      );
    }
    return true;
  }

  function assignTeammate(row, rowEntry) {
    const tbody = row.closest("tbody");
    if (!tbody || !teammateAssignmentAllowed(row, rowEntry, tbody)) {
      return false;
    }
    const teammateId = rowEntry.id ? String(rowEntry.id) : "";
    const teammateGuest = rowEntry.guestName || "";
    const teammateKey = rowEntry.id
      ? `player-${rowEntry.id}`
      : `guest-${normalizeForMatch(rowEntry.guestName)}`;
    row.querySelector('[name="participant_teammate_player_id"]').value = teammateId;
    row.querySelector('[name="participant_teammate_guest_name"]').value = teammateGuest;
    row.dataset.teammateLabel = rowEntry.label;
    row.dataset.teammateKey = teammateKey;
    row.dataset.teammateDetail = detailBadge(rowEntry);
    updateSideLabel(row, getRecordForm(tbody), tbody);
    return true;
  }

  function removeTeammate(row) {
    row.querySelector('[name="participant_teammate_player_id"]').value = "";
    row.querySelector('[name="participant_teammate_guest_name"]').value = "";
    delete row.dataset.teammateLabel;
    delete row.dataset.teammateKey;
    delete row.dataset.teammateDetail;
    const tbody = row.closest("[data-participant-rows]");
    updateSideLabel(row, getRecordForm(tbody), tbody);
  }

  function promoteTeammateToPrimary(row) {
    const teammateId = row.querySelector(
      '[name="participant_teammate_player_id"]'
    ).value;
    const teammateGuest = row.querySelector(
      '[name="participant_teammate_guest_name"]'
    ).value;
    const teammateLabel = row.dataset.teammateLabel || "";
    if (!teammateLabel) {
      return;
    }
    const teammateDetail = row.dataset.teammateDetail || "";

    row.querySelector('[name="participant_player_id"]').value = teammateId;
    row.querySelector('[name="participant_guest_name"]').value = teammateGuest;
    row.dataset.rowKey = teammateId
      ? `player-${teammateId}`
      : `guest-${normalizeForMatch(teammateGuest)}`;
    row.dataset.playerId = teammateId
      ? teammateId
      : `guest:${normalizeForMatch(teammateGuest)}`;
    row.dataset.primaryLabel = teammateLabel;
    row.dataset.primaryDetail = teammateDetail;

    removeTeammate(row);
    const tbody = row.closest("[data-participant-rows]");
    updateSideLabel(row, getRecordForm(tbody), tbody);
  }

  function rosterEntryForRowMember(row, slot, roster) {
    const playerId =
      slot === "primary"
        ? row.querySelector('[name="participant_player_id"]').value.trim()
        : row.querySelector('[name="participant_teammate_player_id"]').value.trim();
    const guestName =
      slot === "primary"
        ? row.querySelector('[name="participant_guest_name"]').value.trim()
        : row.querySelector('[name="participant_teammate_guest_name"]').value.trim();
    if (playerId) {
      const entry = roster.find((item) => String(item.id) === playerId);
      if (entry) {
        return entry;
      }
    }
    const label =
      slot === "primary"
        ? row.dataset.primaryLabel
        : row.dataset.teammateLabel;
    return {
      id: playerId || "",
      label: label || guestName || "Guest",
      username: null,
      kind: playerId ? "member" : "guest",
      guestName: guestName || "",
    };
  }

  function hydrateParticipantRow(row, roster, form, tbody) {
    const body = tbody || row.closest("[data-participant-rows]");
    const gameForm = form || getRecordForm(body);
    if (!row.dataset.primaryLabel) {
      const hydrated = rosterEntryForRowMember(row, "primary", roster);
      row.dataset.primaryLabel = hydrated.label;
      row.dataset.primaryDetail = detailBadge(hydrated);
    }
    const teammateId = row
      .querySelector('[name="participant_teammate_player_id"]')
      ?.value?.trim();
    const teammateGuest = row
      .querySelector('[name="participant_teammate_guest_name"]')
      ?.value?.trim();
    if (teammateId || teammateGuest) {
      if (!row.dataset.teammateLabel) {
        const hydrated = rosterEntryForRowMember(row, "teammate", roster);
        row.dataset.teammateLabel = hydrated.label;
        row.dataset.teammateDetail = detailBadge(hydrated);
      }
      row.dataset.teammateKey = teammateId
        ? `player-${teammateId}`
        : `guest-${normalizeForMatch(teammateGuest)}`;
    }
    initRowMenuDropdown(row);
    updateSideLabel(row, gameForm, body);
  }

  function attachListToInput(input, listEl) {
    let wrap = input.closest(".combobox-input-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.className = "combobox-input-wrap";
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);
    }
    wrap.appendChild(listEl);
    return wrap;
  }

  function viewportHeight() {
    return window.visualViewport?.height ?? window.innerHeight;
  }

  function visibleViewportBounds() {
    const vv = window.visualViewport;
    if (!vv) {
      const height = document.documentElement.clientHeight;
      return { top: 0, left: 0, bottom: height, height };
    }
    return {
      top: vv.offsetTop,
      left: vv.offsetLeft,
      bottom: vv.offsetTop + vv.height,
      height: vv.height,
    };
  }

  function layoutViewportHeight() {
    return document.documentElement.clientHeight;
  }

  function isUsableAnchorRect(rect) {
    return Boolean(rect && rect.width > 0 && rect.height > 0);
  }

  function positionPortaledComboboxList(listEl, input) {
    if (!input || !input.isConnected) {
      return false;
    }
    const rect = input.getBoundingClientRect();
    if (!isUsableAnchorRect(rect)) {
      return false;
    }

    const visible = visibleViewportBounds();
    const preferredHeight = Math.min(240, listEl.scrollHeight || 240);
    const spaceBelow = visible.bottom - rect.bottom;
    const spaceAbove = rect.top - visible.top;
    const placeAbove =
      spaceBelow < preferredHeight && spaceAbove > spaceBelow;
    const available = placeAbove ? spaceAbove : spaceBelow;

    listEl.classList.toggle("combobox-list--above", placeAbove);
    listEl.style.left = `${Math.max(8, rect.left)}px`;
    listEl.style.width = `${Math.max(rect.width, 160)}px`;
    listEl.style.right = "auto";
    listEl.style.maxHeight = `${Math.max(120, available - 8)}px`;

    // iOS: position:fixed uses layout-viewport coordinates; pair layout
    // rect edges with visual-viewport bounds for above/below placement.
    if (placeAbove) {
      listEl.style.top = "auto";
      listEl.style.bottom = `${Math.max(
        8,
        layoutViewportHeight() - rect.top
      )}px`;
    } else {
      listEl.style.bottom = "auto";
      listEl.style.top = `${Math.max(visible.top + 8, rect.bottom)}px`;
    }
    listEl.style.visibility = "visible";
    return true;
  }

  function clearPortaledRepositionTimers(picker) {
    if (!picker.repositionTimers?.length) {
      return;
    }
    picker.repositionTimers.forEach((id) => {
      window.clearTimeout(id);
      window.cancelAnimationFrame(id);
    });
    picker.repositionTimers = [];
  }

  function schedulePortaledComboboxReposition(picker) {
    if (!picker.isOpen || !picker.input) {
      return;
    }
    clearPortaledRepositionTimers(picker);
    picker.repositionTimers = [];

    const run = () => {
      if (picker.isOpen && picker.input) {
        positionPortaledComboboxList(picker.listEl, picker.input);
      }
    };

    let attempts = 0;
    const tryFrame = () => {
      if (!picker.isOpen || !picker.input) {
        return;
      }
      attempts += 1;
      const ok = positionPortaledComboboxList(picker.listEl, picker.input);
      if (!ok && attempts < 6) {
        const frameId = window.requestAnimationFrame(tryFrame);
        picker.repositionTimers.push(frameId);
      }
    };
    picker.repositionTimers.push(window.requestAnimationFrame(tryFrame));
    // iOS: keyboard open and visual-viewport pan settle after focus.
    picker.repositionTimers.push(window.setTimeout(run, 100));
    picker.repositionTimers.push(window.setTimeout(run, 350));
    picker.repositionTimers.push(window.setTimeout(run, 600));
  }

  function adjustListPlacement(listEl, input) {
    listEl.classList.remove("combobox-list--above");
    const inputRect = input.getBoundingClientRect();
    const spaceBelow = viewportHeight() - inputRect.bottom;
    const spaceAbove = inputRect.top;
    const preferredHeight = Math.min(240, listEl.scrollHeight || 240);

    if (spaceBelow < preferredHeight && spaceAbove > spaceBelow) {
      listEl.classList.add("combobox-list--above");
    }

    const available = listEl.classList.contains("combobox-list--above")
      ? spaceAbove
      : spaceBelow;
    listEl.style.maxHeight = `${Math.max(120, available - 8)}px`;
  }

  class PlayerPicker {
    constructor(input, roster, tbody, form) {
      this.input = input;
      this.roster = roster;
      this.tbody = tbody;
      this.form = form;
      this.defaultParticipantScore = form.dataset.defaultParticipantScore ?? "";
      this.suggestions = [];
      this.activeIndex = -1;
      this.isOpen = false;
      this.skipRefresh = false;
      this.suppressBlurCommit = false;

      this.listEl = document.createElement("ul");
      this.listEl.className = "combobox-list";
      this.listEl.setAttribute("role", "listbox");
      this.listEl.hidden = true;
      this.listId = `${input.id || "player-picker"}-suggestions`;
      this.listEl.id = this.listId;
      attachListToInput(input, this.listEl);

      input.setAttribute("role", "combobox");
      input.setAttribute("aria-autocomplete", "list");
      input.setAttribute("aria-expanded", "false");
      input.setAttribute("aria-controls", this.listId);
      suppressBrowserSuggestions(input);

      this.onViewportChange = () => this.reposition();
      input.addEventListener("input", () => this.onInput());
      input.addEventListener("keydown", (event) => this.onKeyDown(event));
      input.addEventListener("blur", () => this.onBlur());
      input.addEventListener("focus", () => this.onFocus());
      window.addEventListener("resize", this.onViewportChange);
      window.visualViewport?.addEventListener("resize", this.onViewportChange);
      window.visualViewport?.addEventListener("scroll", this.onViewportChange);

      // iOS: tapping a non-focusable area (plain text, page background) to
      // dismiss the keyboard does not reliably fire a native blur event, so
      // onBlur alone can miss it. Detect the outside tap directly and
      // commit immediately, before the tap's own focus change happens.
      this.onDocumentPointerDown = (event) => {
        const target = event.target;
        if (!(target instanceof Node)) {
          return;
        }
        if (target === input || input.contains(target)) {
          return;
        }
        if (this.listEl.contains(target)) {
          return;
        }
        if (
          this.collapseButton &&
          (target === this.collapseButton || this.collapseButton.contains(target))
        ) {
          return;
        }
        this.commitPendingEntry();
      };
      document.addEventListener("pointerdown", this.onDocumentPointerDown, true);

      this.panel = form.querySelector("[data-player-picker-panel]");
      this.expandButton = form.querySelector("[data-player-picker-expand]");
      this.collapseButton = form.querySelector("[data-player-picker-collapse]");
      if (this.expandButton) {
        this.expandButton.addEventListener("click", () => this.expandPicker());
      }
      if (this.collapseButton) {
        // Cancelling the picker should not commit whatever was left typed
        // in the input; set this before the click's blur fires.
        this.collapseButton.addEventListener("mousedown", () => {
          this.suppressBlurCommit = true;
        });
        this.collapseButton.addEventListener("click", () => this.collapsePicker());
      }
      tbody.addEventListener("click", (event) => {
        const soloRemoveButton = event.target.closest("[data-remove-side]");
        if (soloRemoveButton) {
          const row = soloRemoveButton.closest("[data-game-row]");
          if (row) {
            this.handleSideAction(row, "remove-side");
          }
          return;
        }
        const actionButton = event.target.closest("[data-side-action]");
        if (actionButton) {
          const row = actionButton.closest("[data-game-row]");
          if (!row) {
            return;
          }
          this.handleSideAction(row, actionButton.dataset.sideAction);
        }
      });
    }

    refreshSideLimitsUI() {
      refreshSideLimitsUI(this.form, this.tbody);
    }

    handleSideAction(row, action) {
      switch (action) {
        case "remove-side":
          row.remove();
          break;
        case "remove-teammate":
          removeTeammate(row);
          break;
        case "remove-primary":
          promoteTeammateToPrimary(row);
          break;
        default:
          return;
      }
      this.refreshSideLimitsUI();
    }

    scheduleSuggestionRefresh() {
      window.requestAnimationFrame(() => {
        if (this.input.value.trim()) {
          this.refreshSuggestions();
        } else {
          this.close();
        }
      });
    }

    isPickerCollapsed() {
      return Boolean(
        this.panel && this.panel.classList.contains("is-player-picker-collapsed")
      );
    }

    expandPicker({ focus = true } = {}) {
      if (!this.panel) {
        return;
      }
      this.panel.classList.remove("is-player-picker-collapsed");
      const expanded = this.form.querySelector("[data-player-picker-expanded]");
      if (expanded) {
        expanded.hidden = false;
      }
      if (this.expandButton) {
        this.expandButton.setAttribute("aria-expanded", "true");
      }
      if (this.collapseButton) {
        this.collapseButton.setAttribute("aria-expanded", "true");
      }
      if (focus) {
        this.input.focus();
      }
    }

    collapsePicker({ focusExpand = true } = {}) {
      if (!this.panel) {
        return;
      }
      this.close();
      this.panel.classList.add("is-player-picker-collapsed");
      const expanded = this.form.querySelector("[data-player-picker-expanded]");
      if (expanded) {
        expanded.hidden = true;
      }
      if (this.expandButton) {
        this.expandButton.setAttribute("aria-expanded", "false");
        if (focusExpand) {
          this.expandButton.focus();
        }
      }
      if (this.collapseButton) {
        this.collapseButton.setAttribute("aria-expanded", "false");
      }
    }

    existingRowKeys() {
      return existingRowKeys(this.tbody);
    }

    onInput() {
      if (this.skipRefresh) {
        this.skipRefresh = false;
        if (!this.input.value.trim()) {
          return;
        }
      }
      this.refreshSuggestions();
    }

    onFocus() {
      if (!this.skipRefresh) {
        this.refreshSuggestions();
      }
    }

    onBlur() {
      // Backstop for onDocumentPointerDown: covers blur triggers that
      // aren't a pointer event (e.g. Tab). tryAddGuestFromInput() clears
      // the input once it commits, so a second call here is a no-op.
      window.setTimeout(() => this.commitPendingEntry(), 150);
    }

    commitPendingEntry() {
      // iOS: dismissing the keyboard, or tapping elsewhere on the page,
      // does not reliably fire a native blur event on the input, so an
      // entry the user typed but never pressed Enter on would otherwise
      // be silently dropped instead of locked in like Enter does.
      // Cancelling via the collapse button opts out via suppressBlurCommit.
      if (this.suppressBlurCommit) {
        this.suppressBlurCommit = false;
      } else {
        this.tryAddGuestFromInput();
      }
      this.close();
    }

    onKeyDown(event) {
      if (!this.isOpen && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
        this.refreshSuggestions();
      }
      if (!this.isOpen) {
        if (event.key === "Enter") {
          event.preventDefault();
          this.tryAddGuestFromInput({ allowGuestCreate: true });
        }
        return;
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        this.moveActive(1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        this.moveActive(-1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        if (this.activeIndex >= 0) {
          this.selectSuggestion(this.suggestions[this.activeIndex]);
        } else {
          this.tryAddGuestFromInput({ allowGuestCreate: true });
        }
      } else if (event.key === "Escape") {
        event.preventDefault();
        this.close();
      }
    }

    moveActive(delta) {
      if (this.suggestions.length === 0) {
        return;
      }
      if (this.activeIndex < 0) {
        this.activeIndex = delta > 0 ? 0 : this.suggestions.length - 1;
      } else {
        this.activeIndex =
          (this.activeIndex + delta + this.suggestions.length) %
          this.suggestions.length;
      }
      this.renderSuggestions();
    }

    refreshSuggestions() {
      const query = this.input.value;
      const trimmed = query.trim();
      const roster = this.roster;
      const existing = this.existingRowKeys();
      const items = [];
      const seenPlayerIds = new Set();
      const seenTeamKeys = new Set();

      const rememberPlayer = (entry) => {
        if (entry?.id) {
          seenPlayerIds.add(Number(entry.id));
        }
      };

      if (trimmed) {
        filterRoster(roster, query)
          .filter((entry) => entry.kind !== "team")
          .filter(
            (entry) =>
              !entryIsIneligible(this.tbody, entry, existing, this.roster)
          )
          .forEach((entry) => {
            if (entry.id && seenPlayerIds.has(Number(entry.id))) {
              return;
            }
            items.push({ type: "player", entry });
            rememberPlayer(entry);
          });
      }

      filterSmartSuggestionsForPlayer(readSmartSuggestions(), this.tbody)
        .filter((suggestion) => smartSuggestionMatchesQuery(suggestion, query))
        .forEach((suggestion) => {
          if (suggestion.kind === "team") {
            const ids = smartPlayerIds(suggestion).sort((a, b) => a - b);
            const teamKey = ids.join("-");
            if (!teamKey || seenTeamKeys.has(teamKey)) {
              return;
            }
            if (ids.some((id) => seenPlayerIds.has(id))) {
              return;
            }
            seenTeamKeys.add(teamKey);
            items.push({
              type: "smart-team",
              label: suggestion.label,
              suggestion,
            });
            ids.forEach((id) => seenPlayerIds.add(id));
            return;
          }
          const entry = rosterEntryFromSmartPlayer(
            roster,
            suggestion.players?.[0]
          );
          if (
            !entry ||
            entryIsIneligible(this.tbody, entry, existing, this.roster)
          ) {
            return;
          }
          if (entry.id && seenPlayerIds.has(Number(entry.id))) {
            return;
          }
          items.push({ type: "smart-solo", entry, label: suggestion.label });
          rememberPlayer(entry);
        });

      if (trimmed) {
        const exactRosterMatch = roster.some((entry) =>
          rosterEntryMatchesLabel(entry, trimmed)
        );
        const guestKey = rowKeyForEntry({ guestName: trimmed });
        const guestAllowed = !existing.has(guestKey);
        if (
          guestAllowed &&
          !exactRosterMatch &&
          !items.some(
            (item) =>
              item.type === "guest" && labelsMatch(item.entry.guestName, trimmed)
          )
        ) {
          items.push({
            type: "guest",
            entry: { guestName: trimmed },
          });
        }
      }

      this.suggestions = items.slice(0, MAX_SUGGESTIONS);
      this.activeIndex = -1;
      if (this.suggestions.length === 0) {
        this.close();
        return;
      }
      this.open();
      this.renderSuggestions();
    }

    renderSuggestions() {
      this.listEl.innerHTML = "";
      this.suggestions.forEach((item, index) => {
        const option = document.createElement("li");
        option.className = "combobox-option";
        option.setAttribute("role", "option");
        option.id = `${this.listId}-opt-${index}`;

        if (item.type === "guest") {
          option.textContent = comboboxOptionHtml(item);
        } else {
          option.innerHTML = comboboxOptionHtml(item);
        }

        if (index === this.activeIndex) {
          option.classList.add("combobox-option--active");
          option.setAttribute("aria-selected", "true");
          this.input.setAttribute("aria-activedescendant", option.id);
        } else {
          option.setAttribute("aria-selected", "false");
        }

        option.addEventListener("mousedown", (event) => {
          event.preventDefault();
          this.selectSuggestion(item);
        });
        this.listEl.appendChild(option);
      });
      this.reposition();
    }

    selectSuggestion(item) {
      if (item.type === "guest") {
        this.addParticipant({
          guestName: item.entry.guestName,
        });
      } else if (item.type === "smart-team") {
        window.LeaderLodgeRecordGame.appendSide({
          players: item.suggestion.players,
        });
      } else {
        this.addParticipant({ entry: item.entry });
      }
      this.skipRefresh = true;
      this.input.value = "";
      this.close();
      this.input.focus();
    }

    tryAddGuestFromInput({ allowGuestCreate = false } = {}) {
      const trimmed = this.input.value.trim();
      if (!trimmed) {
        return;
      }
      const existing = this.existingRowKeys();
      const rosterMatch = this.roster.find(
        (entry) =>
          rosterEntryMatchesLabel(entry, trimmed) &&
          !entryIsIneligible(this.tbody, entry, existing, this.roster)
      );
      if (rosterMatch) {
        this.addParticipant({ entry: rosterMatch });
        this.skipRefresh = true;
        this.input.value = "";
        this.close();
      } else if (allowGuestCreate) {
        this.addParticipant({ guestName: trimmed });
        this.skipRefresh = true;
        this.input.value = "";
        this.close();
      }
    }

    addParticipant({ entry, guestName }) {
      const rowEntry = buildRowEntry({ entry, guestName });

      if (entry?.kind === "team") {
        if (
          entryIsIneligible(
            this.tbody,
            entry,
            this.existingRowKeys(),
            this.roster
          )
        ) {
          return;
        }
        appendTeamRow(
          this.tbody,
          entry,
          this.defaultParticipantScore,
          this.input,
          this.form
        );
        this.refreshSideLimitsUI();
        return;
      }

      if (
        entry &&
        entryIsIneligible(
          this.tbody,
          entry,
          this.existingRowKeys(),
          this.roster
        )
      ) {
        return;
      }
      if (
        appendParticipantRow(
          this.tbody,
          rowEntry,
          this.defaultParticipantScore,
          this.input,
          this.form
        )
      ) {
        this.refreshSideLimitsUI();
      }
    }

    open() {
      this.isOpen = true;
      this.listEl.hidden = false;
      this.input.setAttribute("aria-expanded", "true");
      this.reposition();
    }

    close() {
      this.isOpen = false;
      this.activeIndex = -1;
      this.suggestions = [];
      this.listEl.hidden = true;
      this.listEl.innerHTML = "";
      this.input.setAttribute("aria-expanded", "false");
      this.input.removeAttribute("aria-activedescendant");
    }

    reposition() {
      if (!this.isOpen) {
        return;
      }
      adjustListPlacement(this.listEl, this.input);
    }
  }

  class TeammatePicker {
    constructor(roster, tbody) {
      this.roster = roster.filter((entry) => entry.kind !== "team");
      this.tbody = tbody;
      this.input = null;
      this.row = null;
      this.suggestions = [];
      this.activeIndex = -1;
      this.isOpen = false;
      this.skipRefresh = false;
      this.suppressBlurCommit = false;
      this.placeholder = "Teammate";

      this.listEl = document.createElement("ul");
      this.listEl.className = "combobox-list combobox-list--portal";
      this.listEl.setAttribute("role", "listbox");
      this.listEl.hidden = true;
      this.listId = "teammate-picker-suggestions";
      this.listEl.id = this.listId;
      document.body.appendChild(this.listEl);
      this.repositionTimers = [];

      this.onViewportChange = () => {
        if (this.isOpen && this.input) {
          positionPortaledComboboxList(this.listEl, this.input);
        }
      };
      window.addEventListener("resize", this.onViewportChange);
      window.addEventListener("scroll", this.onViewportChange, true);
      window.visualViewport?.addEventListener("resize", this.onViewportChange);
      window.visualViewport?.addEventListener("scroll", this.onViewportChange);

      // iOS: unlock readonly on touchstart/mousedown before focus so the
      // keyboard opens (and stays) when tapping Teammate, including when
      // switching focus from the footer Add player field.
      const unlockForPointer = (event) => {
        const input = event.target.closest("[data-add-teammate]");
        if (!input || !tbody.contains(input)) {
          return;
        }
        this.prepareInput(input);
        input.removeAttribute("readonly");
      };
      tbody.addEventListener("touchstart", unlockForPointer, {
        passive: true,
        capture: true,
      });
      tbody.addEventListener("mousedown", unlockForPointer, { capture: true });

      tbody.addEventListener("focusin", (event) => {
        const input = event.target.closest("[data-add-teammate]");
        if (input && tbody.contains(input)) {
          this.activate(input);
        }
      });
      tbody.addEventListener("input", (event) => {
        const input = event.target.closest("[data-add-teammate]");
        if (!input || !tbody.contains(input)) {
          return;
        }
        if (input !== this.input) {
          this.activate(input);
        }
        if (input === this.input) {
          this.onInput();
        }
      });
      tbody.addEventListener("keydown", (event) => {
        const input = event.target.closest("[data-add-teammate]");
        if (input && input === this.input) {
          this.onKeyDown(event);
        }
      });
      tbody.addEventListener("focusout", (event) => {
        const input = event.target.closest("[data-add-teammate]");
        if (input && input === this.input) {
          const next = event.relatedTarget;
          if (next && this.listEl.contains(next)) {
            return;
          }
          if (next instanceof Element && next.closest("[data-side-menu-wrap]")) {
            return;
          }
          this.onBlur();
        }
      });
      tbody.addEventListener(
        "pointerdown",
        (event) => {
          if (event.target.closest("[data-side-menu-wrap]")) {
            this.suppressBlurCommit = true;
          }
        },
        true
      );

      // iOS: tapping a non-focusable area (plain text, page background) to
      // dismiss the keyboard does not reliably fire a native blur/focusout
      // event, so onBlur alone can miss it. Detect the outside tap
      // directly and commit immediately, before the tap's own focus
      // change (and activate()'s row switch) happens.
      this.onDocumentPointerDown = (event) => {
        if (!this.input) {
          return;
        }
        const target = event.target;
        if (!(target instanceof Node)) {
          return;
        }
        if (target === this.input || this.input.contains(target)) {
          return;
        }
        if (this.listEl.contains(target)) {
          return;
        }
        if (target instanceof Element && target.closest("[data-side-menu-wrap]")) {
          this.suppressBlurCommit = true;
          return;
        }
        this.commitPendingEntry();
      };
      document.addEventListener("pointerdown", this.onDocumentPointerDown, true);

      tbody.querySelectorAll("[data-add-teammate]").forEach((input) => {
        this.prepareInput(input);
      });
    }

    prepareInput(input) {
      if (!input || input.dataset.teammatePrepared === "1") {
        return;
      }
      input.dataset.teammatePrepared = "1";
      input.setAttribute("role", "combobox");
      input.setAttribute("aria-autocomplete", "list");
      input.setAttribute("aria-expanded", "false");
      input.setAttribute("aria-controls", this.listId);
      suppressBrowserSuggestions(input);
    }

    activate(input) {
      this.prepareInput(input);
      input.removeAttribute("readonly");
      if (this.input === input) {
        this.onFocus();
        return;
      }
      // Commit whatever was pending on the previously active row before
      // switching, in case the tap that moved focus here landed on
      // another teammate field directly (skipping onDocumentPointerDown's
      // outside-tap check, since the tap was on this picker's own input).
      this.commitPendingEntry();
      this.input = input;
      this.row = input.closest("[data-game-row]");
      this.onFocus();
    }

    onInput() {
      if (!this.input) {
        return;
      }
      if (this.skipRefresh) {
        this.skipRefresh = false;
        if (!this.input.value.trim()) {
          return;
        }
      }
      this.refreshSuggestions();
    }

    onFocus() {
      if (!this.skipRefresh) {
        this.refreshSuggestions();
      }
    }

    onBlur() {
      // Backstop for onDocumentPointerDown: covers blur triggers that
      // aren't a pointer event (e.g. Tab). tryAddGuestFromInput() clears
      // the input once it commits, so a second call here is a no-op.
      window.setTimeout(() => this.commitPendingEntry(), 150);
    }

    commitPendingEntry() {
      if (this.suppressBlurCommit) {
        this.suppressBlurCommit = false;
        return;
      }
      this.tryAddGuestFromInput();
      this.close();
    }

    onKeyDown(event) {
      if (!this.isOpen && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
        this.refreshSuggestions();
      }
      if (!this.isOpen) {
        if (event.key === "Enter") {
          event.preventDefault();
          this.tryAddGuestFromInput({ allowGuestCreate: true });
        }
        return;
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        this.moveActive(1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        this.moveActive(-1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        if (this.activeIndex >= 0) {
          this.selectSuggestion(this.suggestions[this.activeIndex]);
        } else {
          this.tryAddGuestFromInput({ allowGuestCreate: true });
        }
      } else if (event.key === "Escape") {
        event.preventDefault();
        this.close();
      }
    }

    moveActive(delta) {
      if (this.suggestions.length === 0) {
        return;
      }
      if (this.activeIndex < 0) {
        this.activeIndex = delta > 0 ? 0 : this.suggestions.length - 1;
      } else {
        this.activeIndex =
          (this.activeIndex + delta + this.suggestions.length) %
          this.suggestions.length;
      }
      this.renderSuggestions();
    }

    refreshSuggestions() {
      if (!this.input || !this.row) {
        return;
      }
      const query = this.input.value;
      const trimmed = query.trim();
      const existing = existingRowKeys(this.tbody);
      const items = [];
      const seenPlayerIds = new Set();

      const rememberPlayer = (entry) => {
        if (entry?.id) {
          seenPlayerIds.add(Number(entry.id));
        }
      };

      if (trimmed) {
        filterRoster(this.roster, query)
          .filter(
            (entry) =>
              !entryIsIneligibleForTeammate(
                this.tbody,
                this.row,
                entry,
                this.roster
              )
          )
          .forEach((entry) => {
            if (entry.id && seenPlayerIds.has(Number(entry.id))) {
              return;
            }
            items.push({ type: "player", entry });
            rememberPlayer(entry);
          });
      }

      filterSmartSuggestionsForTeammate(
        readSmartSuggestions(),
        this.tbody,
        this.row,
        this.roster
      )
        .filter((suggestion) => smartSuggestionMatchesQuery(suggestion, query))
        .forEach((suggestion) => {
          const entry = rosterEntryFromSmartPlayer(
            this.roster,
            suggestion.players?.[0]
          );
          if (
            !entry ||
            entryIsIneligibleForTeammate(
              this.tbody,
              this.row,
              entry,
              this.roster
            )
          ) {
            return;
          }
          if (entry.id && seenPlayerIds.has(Number(entry.id))) {
            return;
          }
          items.push({ type: "smart-solo", entry, label: suggestion.label });
          rememberPlayer(entry);
        });

      if (trimmed) {
        const exactRosterMatch = this.roster.some((entry) =>
          rosterEntryMatchesLabel(entry, trimmed)
        );
        const guestKey = rowKeyForEntry({ guestName: trimmed });
        if (
          !exactRosterMatch &&
          !existing.has(guestKey) &&
          !items.some(
            (item) =>
              item.type === "guest" && labelsMatch(item.entry.guestName, trimmed)
          )
        ) {
          items.push({
            type: "guest",
            entry: { guestName: trimmed },
          });
        }
      }

      this.suggestions = items.slice(0, MAX_SUGGESTIONS);
      this.activeIndex = -1;
      if (this.suggestions.length === 0) {
        this.close();
        return;
      }
      this.open();
      this.renderSuggestions();
    }

    renderSuggestions() {
      if (!this.input) {
        return;
      }
      this.listEl.innerHTML = "";
      this.suggestions.forEach((item, index) => {
        const option = document.createElement("li");
        option.className = "combobox-option";
        option.setAttribute("role", "option");
        option.id = `${this.listId}-opt-${index}`;

        if (item.type === "guest") {
          option.textContent = comboboxOptionHtml(item);
        } else {
          option.innerHTML = comboboxOptionHtml(item);
        }

        if (index === this.activeIndex) {
          option.classList.add("combobox-option--active");
          option.setAttribute("aria-selected", "true");
          this.input.setAttribute("aria-activedescendant", option.id);
        } else {
          option.setAttribute("aria-selected", "false");
        }

        option.addEventListener("mousedown", (event) => {
          event.preventDefault();
          this.selectSuggestion(item);
        });
        this.listEl.appendChild(option);
      });
      this.scheduleReposition();
    }

    selectSuggestion(item) {
      if (item.type === "guest") {
        this.assignFromEntry({ guestName: item.entry.guestName });
      } else {
        this.assignFromEntry({ entry: item.entry });
      }
    }

    tryAddGuestFromInput({ allowGuestCreate = false } = {}) {
      if (!this.input) {
        return;
      }
      const trimmed = this.input.value.trim();
      if (!trimmed) {
        return;
      }
      const rosterMatch = this.roster.find(
        (entry) =>
          rosterEntryMatchesLabel(entry, trimmed) &&
          !entryIsIneligibleForTeammate(
            this.tbody,
            this.row,
            entry,
            this.roster
          )
      );
      if (rosterMatch) {
        this.assignFromEntry({ entry: rosterMatch });
      } else if (allowGuestCreate) {
        this.assignFromEntry({ guestName: trimmed });
      }
    }

    assignFromEntry({ entry, guestName }) {
      if (!this.row || !this.row.isConnected || !this.input) {
        return;
      }
      const row = this.row;
      const input = this.input;
      const rowEntry = buildRowEntry({ entry, guestName });
      const ok = assignTeammate(row, rowEntry);
      this.skipRefresh = true;
      input.value = "";
      this.close();
      if (!ok) {
        input.setAttribute("placeholder", "Player already on a side");
        window.setTimeout(() => {
          input.setAttribute("placeholder", this.placeholder);
        }, 1500);
        input.focus();
        return;
      }
      const scoreInput = row.querySelector("[data-score-input]");
      if (scoreInput) {
        scoreInput.focus();
      }
    }

    open() {
      if (!this.input) {
        return;
      }
      this.isOpen = true;
      this.listEl.hidden = false;
      this.listEl.style.visibility = "hidden";
      this.input.setAttribute("aria-expanded", "true");
      this.scheduleReposition();
    }

    close() {
      this.isOpen = false;
      this.activeIndex = -1;
      this.suggestions = [];
      clearPortaledRepositionTimers(this);
      this.listEl.hidden = true;
      this.listEl.style.visibility = "";
      this.listEl.innerHTML = "";
      if (this.input) {
        this.input.setAttribute("aria-expanded", "false");
        this.input.removeAttribute("aria-activedescendant");
      }
    }

    scheduleReposition() {
      schedulePortaledComboboxReposition(this);
    }

    reposition() {
      if (!this.isOpen || !this.input) {
        return;
      }
      positionPortaledComboboxList(this.listEl, this.input);
    }
  }

  function initPlayerPicker() {
    const form =
      document.getElementById("game-record-form") ||
      document.getElementById("game-edit-form");
    if (!form) {
      return;
    }

    const input = form.querySelector("[data-player-picker]");
    const tbody = form.querySelector("[data-participant-rows]");
    if (!input || !tbody) {
      return;
    }

    let roster = [];
    try {
      const rosterEl = document.getElementById("game-roster-data");
      roster = rosterEl ? JSON.parse(rosterEl.textContent) : [];
    } catch (_error) {
      roster = [];
    }

    window.LeaderLodgeRecordGame = window.LeaderLodgeRecordGame || {};
    window.LeaderLodgeRecordGame.picker = new PlayerPicker(
      input,
      roster,
      tbody,
      form
    );
    window.LeaderLodgeRecordGame.teammatePicker = new TeammatePicker(
      roster,
      tbody
    );

    form.addEventListener("submit", () => {
      window.LeaderLodgeRecordGame.picker?.commitPendingEntry?.();
      window.LeaderLodgeRecordGame.teammatePicker?.commitPendingEntry?.();
    });

    tbody.querySelectorAll("[data-game-row]").forEach((row) => {
      hydrateParticipantRow(row, roster, form, tbody);
    });
    refreshSideLimitsUI(form, tbody);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPlayerPicker);
  } else {
    initPlayerPicker();
  }

  window.LeaderLodgeRecordGame = window.LeaderLodgeRecordGame || {};
  window.LeaderLodgeRecordGame.collapsePlayerPicker = function collapsePlayerPicker() {
    const picker = window.LeaderLodgeRecordGame.picker;
    if (picker && typeof picker.collapsePicker === "function") {
      // Don't steal focus from AI status / Save after a successful parse.
      picker.collapsePicker({ focusExpand: false });
    }
  };
  window.LeaderLodgeRecordGame.clearParticipants = function clearParticipants() {
    const tbody = document.querySelector("[data-participant-rows]");
    if (!tbody) {
      return;
    }
    tbody.querySelectorAll("[data-game-row]").forEach((row) => row.remove());
    const empty = tbody.querySelector("[data-participant-empty]");
    if (empty) {
      empty.classList.remove("d-none");
    }
  };
  window.LeaderLodgeRecordGame.appendSide = function appendSide(side) {
    const form =
      document.getElementById("game-record-form") ||
      document.getElementById("game-edit-form");
    const tbody = form?.querySelector("[data-participant-rows]");
    if (!form || !tbody || !side || !Array.isArray(side.players)) {
      return false;
    }
    if (!canAddSide(form, tbody)) {
      return false;
    }
    const empty = tbody.querySelector("[data-participant-empty]");
    if (empty) {
      empty.classList.add("d-none");
    }
    const fallback = form.dataset.defaultParticipantScore || "";
    const scoreValue =
      side.score != null && side.score !== "" ? String(side.score) : fallback;
    const players = side.players.filter((p) => p && (p.player_id || p.guest_name));
    if (!players.length) {
      return false;
    }
    const primary = {
      id: players[0].player_id || "",
      guestName: players[0].guest_name || "",
      label: players[0].label || players[0].guest_name || "Player",
      kind: players[0].player_id ? "member" : "guest",
      username: null,
    };
    if (!appendParticipantRow(tbody, primary, scoreValue, null, form)) {
      return false;
    }
    const rows = tbody.querySelectorAll("[data-game-row]");
    const row = rows[rows.length - 1];
    if (players.length > 1) {
      const teammate = {
        id: players[1].player_id || "",
        guestName: players[1].guest_name || "",
        label: players[1].label || players[1].guest_name || "Teammate",
        kind: players[1].player_id ? "member" : "guest",
        username: null,
      };
      assignTeammate(row, teammate);
    }
    const scoreInput = row.querySelector("[data-score-input]");
    if (scoreInput && side.score != null && side.score !== "") {
      scoreInput.value = String(side.score);
      scoreInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
    window.LeaderLodgeRecordGame?.picker?.refreshSideLimitsUI?.();
    return true;
  };
})();
