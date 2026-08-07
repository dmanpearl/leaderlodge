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

  function playersAlreadyInGame(tbody) {
    const ids = new Set();
    tbody.querySelectorAll("[data-game-row]").forEach((row) => {
      const primaryHidden = row.querySelector('[name="participant_player_id"]');
      const primaryValue = primaryHidden ? primaryHidden.value.trim() : "";
      if (primaryValue) {
        ids.add(Number(primaryValue));
      } else {
        const primaryId = row.dataset.playerId;
        if (primaryId && !primaryId.startsWith("guest:")) {
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

  function sideLabel(primaryLabel, teammateLabel) {
    if (!teammateLabel) {
      return primaryLabel;
    }
    return [primaryLabel, teammateLabel]
      .sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))
      .join("+");
  }

  function updateSideLabel(row) {
    const labelEl = row.querySelector("[data-side-label]");
    if (!labelEl) {
      return;
    }
    const primaryLabel =
      row.dataset.primaryLabel || labelEl.dataset.primaryLabel || "";
    const teammateLabel = row.dataset.teammateLabel || "";
    const hasTeammate = Boolean(teammateLabel);
    labelEl.innerHTML = `${sideLabel(primaryLabel, teammateLabel)}${
      hasTeammate
        ? ' <span class="badge text-bg-primary ms-1">Team</span>'
        : row.dataset.primaryDetail
          ? ` <span class="text-muted small ms-1">${row.dataset.primaryDetail}</span>`
          : ""
    }`;
    const addBtn = row.querySelector("[data-add-teammate]");
    if (addBtn) {
      addBtn.classList.toggle("d-none", hasTeammate);
    }
    row.dataset.hasTeammate = hasTeammate ? "1" : "";
  }

  function appendParticipantRow(tbody, rowEntry, defaultParticipantScore, focusEl) {
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
    const detail =
      rowEntry.username ||
      (rowEntry.id && rowEntry.kind === "guest"
        ? "Guest"
        : rowEntry.id
          ? ""
          : "New guest");
    row.dataset.primaryDetail =
      detail === "Guest" || detail === "New guest"
        ? `<span class="badge text-bg-secondary">${detail}</span>`
        : detail
          ? `(${detail})`
          : "";

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
              <button type="button" class="btn btn-sm btn-outline-primary" data-add-teammate><span class="d-none d-sm-inline">Add Teammate</span><span class="d-sm-none">+ Teammate</span></button>
              <button type="button" class="btn btn-sm btn-outline-secondary" data-remove-participant aria-label="Remove player">&times;</button>
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
    const scoreInput = row.querySelector("[data-score-input]");
    if (defaultParticipantScore !== "") {
      scoreInput.value = defaultParticipantScore;
    }
    if (focusEl) {
      focusEl.focus();
    }
    return true;
  }

  function appendTeamRow(tbody, entry, defaultParticipantScore, focusEl) {
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
      null
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

  function assignTeammate(row, rowEntry) {
    const teammateId = rowEntry.id ? String(rowEntry.id) : "";
    const teammateGuest = rowEntry.guestName || "";
    const teammateKey = rowEntry.id
      ? `player-${rowEntry.id}`
      : `guest-${normalizeForMatch(rowEntry.guestName)}`;
    if (row.dataset.rowKey === teammateKey) {
      return false;
    }
    const tbody = row.closest("tbody");
    if (tbody && rowEntry.id && playersAlreadyInGame(tbody).has(Number(rowEntry.id))) {
      const primaryId = row.dataset.playerId;
      const onThisRow =
        (primaryId && Number(primaryId) === Number(rowEntry.id)) ||
        row.dataset.rowKey === teammateKey;
      if (!onThisRow) {
        return false;
      }
    }
    if (tbody && existingRowKeys(tbody).has(teammateKey) && row.dataset.rowKey !== teammateKey) {
      // Teammate already on another side.
      const alreadyOnSide = Array.from(tbody.querySelectorAll("[data-game-row]")).some(
        (other) =>
          other !== row &&
          (other.dataset.rowKey === teammateKey ||
            other.dataset.teammateKey === teammateKey)
      );
      if (alreadyOnSide) {
        return false;
      }
    }
    row.querySelector('[name="participant_teammate_player_id"]').value = teammateId;
    row.querySelector('[name="participant_teammate_guest_name"]').value = teammateGuest;
    row.dataset.teammateLabel = rowEntry.label;
    row.dataset.teammateKey = teammateKey;
    updateSideLabel(row);
    return true;
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
      this.addPlayerLabelText = "Add player";
      this.addTeammateLabelText = "Add Teammate";
      this.pickerLabelTextEl = form.querySelector("[data-player-picker-label-text]");
      this.pickerExpandedEl = form.querySelector("[data-player-picker-expanded]");
      this.suggestions = [];
      this.activeIndex = -1;
      this.isOpen = false;
      this.skipRefresh = false;

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

      this.teammateTargetRow = null;
      this.panel = form.querySelector("[data-player-picker-panel]");
      this.expandButton = form.querySelector("[data-player-picker-expand]");
      this.collapseButton = form.querySelector("[data-player-picker-collapse]");
      if (this.expandButton) {
        this.expandButton.addEventListener("click", () => this.expandPicker());
      }
      if (this.collapseButton) {
        this.collapseButton.addEventListener("click", () => this.collapsePicker());
      }
      tbody.addEventListener("click", (event) => {
        const addTeammate = event.target.closest("[data-add-teammate]");
        if (addTeammate) {
          const row = addTeammate.closest("[data-game-row]");
          if (row) {
            this.setTeammateTarget(row);
          }
          return;
        }
        const button = event.target.closest("[data-remove-participant]");
        if (!button) {
          return;
        }
        const row = button.closest("[data-game-row]");
        if (row) {
          if (this.teammateTargetRow === row) {
            this.clearTeammateTarget();
          }
          row.remove();
          this.scheduleSuggestionRefresh();
        }
      });
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
      window.setTimeout(() => this.close(), 150);
    }

    onKeyDown(event) {
      if (!this.isOpen && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
        this.refreshSuggestions();
      }
      if (!this.isOpen) {
        if (event.key === "Enter") {
          event.preventDefault();
          this.tryAddGuestFromInput();
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
          this.tryAddGuestFromInput();
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

    isPickingTeammate() {
      return Boolean(this.teammateTargetRow && this.teammateTargetRow.isConnected);
    }

    rosterForCurrentMode() {
      // Teammates must be individual people; existing teams cannot nest as a
      // teammate on another side.
      if (this.isPickingTeammate()) {
        return this.roster.filter((entry) => entry.kind !== "team");
      }
      return this.roster;
    }

    refreshSuggestions() {
      const query = this.input.value;
      const roster = this.rosterForCurrentMode();
      const matches = filterRoster(roster, query);
      const existing = this.existingRowKeys();
      this.suggestions = matches
        .filter(
          (entry) =>
            !entryIsIneligible(this.tbody, entry, existing, this.roster)
        )
        .map((entry) => ({ type: "player", entry }));

      const trimmed = query.trim();
      if (trimmed) {
        const exactRosterMatch = roster.some((entry) =>
          rosterEntryMatchesLabel(entry, trimmed)
        );
        const guestKey = rowKeyForEntry({ guestName: trimmed });
        if (
          !exactRosterMatch &&
          !existing.has(guestKey) &&
          !this.suggestions.some(
            (item) =>
              item.type === "guest" && labelsMatch(item.entry.guestName, trimmed)
          )
        ) {
          this.suggestions.push({
            type: "guest",
            entry: { guestName: trimmed },
          });
        }
      }

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
          option.textContent = `Add guest "${item.entry.guestName}"`;
        } else {
          const entry = item.entry;
          const detail =
            entry.kind === "team"
              ? "team"
              : entry.username
                ? entry.username
                : entry.kind === "guest"
                  ? "guest"
                  : "";
          option.innerHTML = `<span>${entry.label}</span>${
            detail
              ? ` <span class="text-muted small">${detail}</span>`
              : ""
          }`;
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
      } else {
        this.addParticipant({ entry: item.entry });
      }
      this.skipRefresh = true;
      this.input.value = "";
      this.close();
      this.input.focus();
    }

    tryAddGuestFromInput() {
      const trimmed = this.input.value.trim();
      if (!trimmed) {
        return;
      }
      const existing = this.existingRowKeys();
      const roster = this.rosterForCurrentMode();
      const rosterMatch = roster.find(
        (entry) =>
          rosterEntryMatchesLabel(entry, trimmed) &&
          !entryIsIneligible(this.tbody, entry, existing, this.roster)
      );
      if (rosterMatch) {
        this.addParticipant({ entry: rosterMatch });
      } else {
        this.addParticipant({ guestName: trimmed });
      }
      this.skipRefresh = true;
      this.input.value = "";
      this.close();
    }

    addParticipant({ entry, guestName }) {
      const teammateRow = this.teammateTargetRow;
      if (entry?.kind === "team") {
        // Teams are only valid as whole sides, never as a teammate pick.
        if (teammateRow && teammateRow.isConnected) {
          return;
        }
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
          this.input
        );
        this.scheduleSuggestionRefresh();
        return;
      }

      const rowEntry = buildRowEntry({ entry, guestName });
      if (teammateRow && teammateRow.isConnected) {
        const ok = assignTeammate(teammateRow, rowEntry);
        this.clearTeammateTarget();
        if (!ok) {
          this.input.setAttribute(
            "placeholder",
            "Player already on a side"
          );
          window.setTimeout(() => {
            this.input.setAttribute("placeholder", "Type player");
          }, 1500);
        } else {
          this.scheduleSuggestionRefresh();
        }
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
          this.input
        )
      ) {
        this.scheduleSuggestionRefresh();
      }
    }

    setPickerLabelText(text) {
      if (this.pickerLabelTextEl) {
        this.pickerLabelTextEl.textContent = text;
      }
    }

    setTeammateTarget(row) {
      this.teammateTargetRow = row;
      this.setPickerLabelText(this.addTeammateLabelText);
      this.pickerExpandedEl?.classList.add("player-picker-cta--teammate");
      this.input.setAttribute("placeholder", "Type teammate");
      this.expandPicker({ focus: true });
    }

    clearTeammateTarget() {
      this.teammateTargetRow = null;
      this.setPickerLabelText(this.addPlayerLabelText);
      this.pickerExpandedEl?.classList.remove("player-picker-cta--teammate");
      this.input.setAttribute("placeholder", "Type player");
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

  function initPlayerPicker() {
    const form = document.getElementById("game-record-form");
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
    const form = document.getElementById("game-record-form");
    const tbody = document.querySelector("[data-participant-rows]");
    if (!form || !tbody || !side || !Array.isArray(side.players)) {
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
    if (!appendParticipantRow(tbody, primary, scoreValue, null)) {
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
    return true;
  };
})();
