/**
 * Fuzzy player picker for game recording — roster members and guests.
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
        return { entry, score: bestScore };
      })
      .filter((item) => item.score >= 0)
      .sort((a, b) => {
        if (b.score !== a.score) {
          return b.score - a.score;
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
              <button type="button" class="btn btn-sm btn-outline-primary" data-add-teammate>Add Teammate</button>
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

      this.onViewportChange = () => this.reposition();
      input.addEventListener("input", () => this.onInput());
      input.addEventListener("keydown", (event) => this.onKeyDown(event));
      input.addEventListener("blur", () => this.onBlur());
      input.addEventListener("focus", () => this.onFocus());
      window.addEventListener("resize", this.onViewportChange);
      window.visualViewport?.addEventListener("resize", this.onViewportChange);
      window.visualViewport?.addEventListener("scroll", this.onViewportChange);

      this.teammateTargetRow = null;
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
        }
      });
    }

    existingRowKeys() {
      return existingRowKeys(this.tbody);
    }

    onInput() {
      if (this.skipRefresh) {
        this.skipRefresh = false;
        return;
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

    refreshSuggestions() {
      const query = this.input.value;
      const matches = filterRoster(this.roster, query);
      const existing = this.existingRowKeys();
      this.suggestions = matches
        .filter((entry) => !existing.has(rowKeyForEntry({ id: entry.id })))
        .map((entry) => ({ type: "player", entry }));

      const trimmed = query.trim();
      if (trimmed) {
        const exactRosterMatch = this.roster.some(
          (entry) =>
            labelsMatch(entry.label, trimmed) ||
            (entry.username && labelsMatch(entry.username, trimmed))
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
          const detail = entry.username
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
      const rosterMatch = this.roster.find(
        (entry) =>
          labelsMatch(entry.label, trimmed) ||
          (entry.username && labelsMatch(entry.username, trimmed))
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
      const rowEntry = buildRowEntry({ entry, guestName });
      const teammateRow = this.teammateTargetRow;
      if (teammateRow && teammateRow.isConnected) {
        const ok = assignTeammate(teammateRow, rowEntry);
        this.clearTeammateTarget();
        if (!ok) {
          this.input.setAttribute(
            "placeholder",
            "Player already on a side"
          );
          window.setTimeout(() => {
            this.input.setAttribute("placeholder", "Type player name");
          }, 1500);
        }
        return;
      }
      appendParticipantRow(
        this.tbody,
        rowEntry,
        this.defaultParticipantScore,
        this.input
      );
    }

    setPickerLabelText(text) {
      if (this.pickerLabelTextEl) {
        this.pickerLabelTextEl.textContent = text;
      }
    }

    setTeammateTarget(row) {
      this.teammateTargetRow = row;
      this.setPickerLabelText(this.addTeammateLabelText);
      this.input.setAttribute("placeholder", "Type teammate name");
      this.input.focus();
    }

    clearTeammateTarget() {
      this.teammateTargetRow = null;
      this.setPickerLabelText(this.addPlayerLabelText);
      this.input.setAttribute("placeholder", "Type player name");
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

    new PlayerPicker(input, roster, tbody, form);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPlayerPicker);
  } else {
    initPlayerPicker();
  }
})();
