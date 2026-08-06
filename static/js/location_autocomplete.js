/**
 * Fuzzy location combobox for game recording setup.
 * Suggestions match accent-insensitively; submitted text is unchanged unless
 * the user picks a suggestion (canonical stored name).
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

  function scoreLocation(query, name) {
    const q = normalizeForMatch(query);
    const n = normalizeForMatch(name);
    if (!q) {
      return -1;
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

  function filterLocations(locations, query) {
    if (!query.trim()) {
      return [];
    }

    return locations
      .map((location) => ({
        location,
        score: scoreLocation(query, location.name),
      }))
      .filter((item) => item.score >= 0)
      .sort((a, b) => {
        if (b.score !== a.score) {
          return b.score - a.score;
        }
        return a.location.name.localeCompare(b.location.name);
      })
      .slice(0, MAX_SUGGESTIONS)
      .map((item) => item.location);
  }

  function recentSuggestions(recentLocations) {
    return recentLocations.slice(0, MAX_SUGGESTIONS);
  }

  function attachListToInput(input, listEl) {
    const existingWrap = input.closest(".location-field-input-wrap");
    if (existingWrap) {
      existingWrap.appendChild(listEl);
      return existingWrap;
    }

    const wrap = document.createElement("div");
    wrap.className = "combobox-input-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    wrap.appendChild(listEl);
    return wrap;
  }

  function syncLocationFieldButtons(input) {
    const field = input.closest("[data-location-field]");
    if (!field) {
      return;
    }
    const hasValue = Boolean(input.value.trim());
    const clearButton = field.querySelector("[data-location-clear]");
    const searchButton = field.querySelector("[data-location-search]");
    if (clearButton) {
      clearButton.hidden = !hasValue;
    }
    if (searchButton) {
      searchButton.hidden = !hasValue;
    }
  }

  function initLocationClearButton(input) {
    const field = input.closest("[data-location-field]");
    const clearButton = field?.querySelector("[data-location-clear]");
    if (!clearButton) {
      return;
    }

    clearButton.addEventListener("mousedown", (event) => {
      event.preventDefault();
    });
    clearButton.addEventListener("click", () => {
      input.value = "";
      syncLocationFieldButtons(input);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
    });
    syncLocationFieldButtons(input);
  }

  function viewportHeight() {
    return window.visualViewport?.height ?? window.innerHeight;
  }

  function adjustListPlacement(listEl, input) {
    listEl.classList.remove("location-autocomplete-list--above");
    const inputRect = input.getBoundingClientRect();
    const spaceBelow = viewportHeight() - inputRect.bottom;
    const spaceAbove = inputRect.top;
    const preferredHeight = Math.min(240, listEl.scrollHeight || 240);

    if (spaceBelow < preferredHeight && spaceAbove > spaceBelow) {
      listEl.classList.add("location-autocomplete-list--above");
    }

    const available = listEl.classList.contains("location-autocomplete-list--above")
      ? spaceAbove
      : spaceBelow;
    listEl.style.maxHeight = `${Math.max(120, available - 8)}px`;
  }

  class LocationAutocomplete {
    constructor(input, groupSelect, locationsUrlTemplate, fixedGroupId = "") {
      this.input = input;
      this.groupSelect = groupSelect;
      this.fixedGroupId = fixedGroupId;
      this.locationsUrlTemplate = locationsUrlTemplate;
      this.form = input.closest("form");
      this.gameSelect = this.form
        ? this.form.querySelector('[name="game_type_code"]')
        : null;
      this.recentButton = this.form
        ? this.form.querySelector("[data-location-recent]")
        : null;
      this.locations = [];
      this.recentLocations = [];
      this.suggestions = [];
      this.activeIndex = -1;
      this.isOpen = false;
      this.skipRefresh = false;
      this.forceRecent = false;

      this.listEl = document.createElement("ul");
      this.listEl.className = "location-autocomplete-list";
      this.listEl.setAttribute("role", "listbox");
      this.listEl.hidden = true;
      this.listId = `${input.id || "location"}-suggestions`;
      this.listEl.id = this.listId;
      attachListToInput(input, this.listEl);

      this.input.setAttribute("role", "combobox");
      this.input.setAttribute("aria-autocomplete", "list");
      this.input.setAttribute("aria-expanded", "false");
      this.input.setAttribute("aria-controls", this.listId);

      this.onInput = this.onInput.bind(this);
      this.onKeyDown = this.onKeyDown.bind(this);
      this.onBlur = this.onBlur.bind(this);
      this.onFocus = this.onFocus.bind(this);
      this.reposition = this.reposition.bind(this);
      this.onGroupChange = this.onGroupChange.bind(this);
      this.onGameTypeChange = this.onGameTypeChange.bind(this);
      this.onRecentClick = this.onRecentClick.bind(this);
      this.onViewportChange = this.reposition;

      this.input.addEventListener("input", this.onInput);
      this.input.addEventListener("keydown", this.onKeyDown);
      this.input.addEventListener("blur", this.onBlur);
      this.input.addEventListener("focus", this.onFocus);
      window.addEventListener("resize", this.onViewportChange);
      window.visualViewport?.addEventListener("resize", this.onViewportChange);
      window.visualViewport?.addEventListener("scroll", this.onViewportChange);
      if (this.groupSelect) {
        this.groupSelect.addEventListener("change", this.onGroupChange);
      }
      if (this.gameSelect) {
        this.gameSelect.addEventListener("change", this.onGameTypeChange);
      }
      if (this.recentButton) {
        this.recentButton.addEventListener("mousedown", (event) => {
          event.preventDefault();
        });
        this.recentButton.addEventListener("click", this.onRecentClick);
      }

      initLocationClearButton(this.input);
      this.loadLocationsForSelectedGroup();
    }

    locationsUrl(groupId) {
      const base = this.locationsUrlTemplate.replace("/0/", `/${groupId}/`);
      const gameType = this.gameSelect ? this.gameSelect.value : "";
      if (!gameType) {
        return base;
      }
      const params = new URLSearchParams({ game_type_code: gameType });
      return `${base}?${params.toString()}`;
    }

    syncRecentButton() {
      if (!this.recentButton) {
        return;
      }
      this.recentButton.disabled = this.recentLocations.length === 0;
    }

    async loadLocationsForSelectedGroup() {
      const groupId = this.groupSelect ? this.groupSelect.value : this.fixedGroupId;
      if (!groupId) {
        this.locations = [];
        this.recentLocations = [];
        this.syncRecentButton();
        this.close();
        return;
      }

      try {
        const response = await fetch(this.locationsUrl(groupId), {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          this.locations = [];
          this.recentLocations = [];
          this.syncRecentButton();
          this.close();
          return;
        }
        const data = await response.json();
        this.locations = Array.isArray(data.locations) ? data.locations : [];
        this.recentLocations = Array.isArray(data.recent) ? data.recent : [];
        this.syncRecentButton();
      } catch (_error) {
        this.locations = [];
        this.recentLocations = [];
        this.syncRecentButton();
        this.close();
      }
    }

    onGroupChange() {
      this.loadLocationsForSelectedGroup();
    }

    onGameTypeChange() {
      this.loadLocationsForSelectedGroup();
    }

    onRecentClick() {
      if (this.recentLocations.length === 0) {
        return;
      }
      this.forceRecent = true;
      this.input.focus();
      this.refreshSuggestions({ forceRecent: true });
    }

    onInput(event) {
      syncLocationFieldButtons(this.input);
      this.forceRecent = false;
      if (this.skipRefresh) {
        this.skipRefresh = false;
        return;
      }
      if (event && !event.isTrusted) {
        return;
      }
      this.refreshSuggestions();
    }

    onFocus() {
      if (this.skipRefresh) {
        return;
      }
      this.refreshSuggestions({ forceRecent: this.forceRecent });
    }

    onBlur() {
      window.setTimeout(() => {
        this.close();
      }, 150);
    }

    onKeyDown(event) {
      if (!this.isOpen && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
        this.refreshSuggestions();
      }
      if (!this.isOpen) {
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

    refreshSuggestions({ forceRecent = false } = {}) {
      const query = this.input.value.trim();
      if (forceRecent || !query) {
        this.suggestions = recentSuggestions(this.recentLocations);
      } else {
        this.suggestions = filterLocations(this.locations, this.input.value);
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
      this.suggestions.forEach((location, index) => {
        const item = document.createElement("li");
        item.className = "location-autocomplete-option";
        item.setAttribute("role", "option");
        item.textContent = location.name;
        if (index === this.activeIndex) {
          item.classList.add("location-autocomplete-option--active");
          item.setAttribute("aria-selected", "true");
          this.input.setAttribute("aria-activedescendant", `${this.listId}-opt-${index}`);
        } else {
          item.setAttribute("aria-selected", "false");
        }
        item.id = `${this.listId}-opt-${index}`;
        item.addEventListener("mousedown", (event) => {
          event.preventDefault();
          this.selectSuggestion(location);
        });
        this.listEl.appendChild(item);
      });
      this.reposition();
    }

    selectSuggestion(location) {
      this.skipRefresh = true;
      this.input.value = location.name;
      syncLocationFieldButtons(this.input);
      this.input.dispatchEvent(
        new CustomEvent("location-autocomplete-select", {
          bubbles: true,
          detail: { name: location.name },
        }),
      );
      this.close();
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

  function initLocationAutocomplete() {
    const urlTemplate = document.body.dataset.locationsUrlTemplate;
    if (!urlTemplate) {
      return;
    }

    document.querySelectorAll("[data-location-autocomplete]").forEach((input) => {
      const form = input.closest("form");
      const groupSelect = form ? form.querySelector('[name="group"]') : null;
      const fixedGroupId =
        form?.dataset.locationGroupId || input.dataset.locationGroupId || "";
      new LocationAutocomplete(input, groupSelect, urlTemplate, fixedGroupId);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLocationAutocomplete);
  } else {
    initLocationAutocomplete();
  }
})();
