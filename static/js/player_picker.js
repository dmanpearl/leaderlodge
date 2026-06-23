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

      this.listEl = document.createElement("ul");
      this.listEl.className = "combobox-list";
      this.listEl.setAttribute("role", "listbox");
      this.listEl.hidden = true;
      this.listId = `${input.id || "player-picker"}-suggestions`;
      this.listEl.id = this.listId;
      document.body.appendChild(this.listEl);

      input.setAttribute("role", "combobox");
      input.setAttribute("aria-autocomplete", "list");
      input.setAttribute("aria-expanded", "false");
      input.setAttribute("aria-controls", this.listId);

      input.addEventListener("input", () => this.onInput());
      input.addEventListener("keydown", (event) => this.onKeyDown(event));
      input.addEventListener("blur", () => this.onBlur());
      input.addEventListener("focus", () => this.onFocus());
      window.addEventListener("resize", () => this.reposition());
      window.addEventListener("scroll", () => this.reposition(), true);

      tbody.addEventListener("click", (event) => {
        const button = event.target.closest("[data-remove-participant]");
        if (!button) {
          return;
        }
        const row = button.closest("[data-game-row]");
        if (row) {
          row.remove();
        }
      });
    }

    existingRowKeys() {
      return new Set(
        Array.from(this.tbody.querySelectorAll("[data-game-row]")).map(
          (row) => row.dataset.rowKey
        )
      );
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
      } else if (event.key === "Enter" && this.activeIndex >= 0) {
        event.preventDefault();
        this.selectSuggestion(this.suggestions[this.activeIndex]);
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
      let rowEntry;
      if (entry) {
        rowEntry = {
          id: entry.id,
          label: entry.label,
          username: entry.username,
          kind: entry.kind,
          guestName: "",
        };
      } else {
        rowEntry = {
          id: "",
          label: guestName,
          username: null,
          kind: "guest",
          guestName,
        };
      }

      const rowKey = rowKeyForEntry(
        rowEntry.id ? { id: rowEntry.id } : { guestName: rowEntry.guestName }
      );
      if (this.existingRowKeys().has(rowKey)) {
        return;
      }

      const row = document.createElement("tr");
      row.setAttribute("data-game-row", "");
      row.dataset.rowKey = rowKey;
      row.dataset.playerId = rowEntry.id
        ? String(rowEntry.id)
        : `guest:${normalizeForMatch(rowEntry.guestName)}`;

      const initialScoreAttr = this.defaultParticipantScore
        ? ` data-initial-score="${this.defaultParticipantScore}"`
        : "";

      const detail =
        rowEntry.username ||
        (rowEntry.id && rowEntry.kind === "guest" ? "Guest" : rowEntry.id ? "" : "New guest");

      row.innerHTML = `
        <td>
          <div class="d-flex align-items-center justify-content-between gap-2 participant-label">
            <span>
              ${rowEntry.label}
              ${
                detail
                  ? `<span class="text-muted small ms-1">${detail === "Guest" || detail === "New guest" ? `<span class="badge text-bg-secondary">${detail}</span>` : `(${detail})`}</span>`
                  : ""
              }
            </span>
            <button type="button" class="btn btn-sm btn-outline-secondary flex-shrink-0" data-remove-participant aria-label="Remove player">&times;</button>
          </div>
          <input type="hidden" name="participant_player_id" value="${rowEntry.id || ""}" />
          <input type="hidden" name="participant_guest_name" value="${rowEntry.guestName || ""}" />
        </td>
        <td>
          <input
            type="text"
            inputmode="numeric"
            name="participant_score"
            class="form-control form-control-sm"
            data-score-input${initialScoreAttr}
            value="${this.defaultParticipantScore}"
            style="max-width: 6rem;"
          />
        </td>
        <td data-result-cell></td>
      `;

      this.tbody.appendChild(row);
      const scoreInput = row.querySelector("[data-score-input]");
      if (this.defaultParticipantScore !== "") {
        scoreInput.value = this.defaultParticipantScore;
      }
      this.input.focus();
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
      const rect = this.input.getBoundingClientRect();
      this.listEl.style.top = `${rect.bottom}px`;
      this.listEl.style.left = `${rect.left}px`;
      this.listEl.style.width = `${rect.width}px`;
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
