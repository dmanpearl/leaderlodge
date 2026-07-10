(function () {
  function normalizeForMatch(value) {
    return value
      .normalize("NFD")
      .replace(/\p{M}/gu, "")
      .trim()
      .toLowerCase();
  }

  function filterGuests(guests, query) {
    const q = normalizeForMatch(query);
    if (!q) {
      return guests.slice();
    }
    return guests.filter((g) => normalizeForMatch(g.name).includes(q));
  }

  class InviteNameCombobox {
    constructor(input, hiddenField, guests) {
      this.input = input;
      this.hiddenField = hiddenField;
      this.guests = guests;
      this.suggestions = [];
      this.activeIndex = -1;
      this.isOpen = false;
      this.selectedGuest = null;

      this.listEl = document.createElement("ul");
      this.listEl.className = "invite-name-dropdown";
      this.listEl.setAttribute("role", "listbox");
      this.listEl.hidden = true;
      this.listId = "invite-name-dropdown-list";
      this.listEl.id = this.listId;

      this.helperText = document.createElement("span");
      this.helperText.className = "invite-guest-selected-hint";
      this.helperText.hidden = true;

      const wrap = document.createElement("div");
      wrap.className = "invite-name-field";
      this.input.parentNode.insertBefore(wrap, this.input);
      wrap.appendChild(this.input);
      wrap.appendChild(this.listEl);
      wrap.appendChild(this.helperText);

      this.input.setAttribute("role", "combobox");
      this.input.setAttribute("aria-autocomplete", "list");
      this.input.setAttribute("aria-expanded", "false");
      this.input.setAttribute("aria-controls", this.listId);

      this.input.addEventListener("input", this.onInput.bind(this));
      this.input.addEventListener("keydown", this.onKeyDown.bind(this));
      this.input.addEventListener("focus", this.onFocus.bind(this));
      this.input.addEventListener("blur", () => setTimeout(() => this.close(), 150));
    }

    onInput(event) {
      if (!event.isTrusted) return;
      if (this.selectedGuest !== null) {
        this.clearSelection();
      }
      this.refreshSuggestions();
    }

    onFocus() {
      this.refreshSuggestions();
    }

    onKeyDown(event) {
      if (!this.isOpen) {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          this.refreshSuggestions();
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
        this.select(this.suggestions[this.activeIndex]);
      } else if (event.key === "Escape") {
        event.preventDefault();
        this.close();
      }
    }

    moveActive(delta) {
      if (!this.suggestions.length) return;
      if (this.activeIndex < 0) {
        this.activeIndex = delta > 0 ? 0 : this.suggestions.length - 1;
      } else {
        this.activeIndex =
          (this.activeIndex + delta + this.suggestions.length) %
          this.suggestions.length;
      }
      this.render();
    }

    refreshSuggestions() {
      const matched = filterGuests(this.guests, this.input.value);
      this.suggestions = matched.map((g) => ({ kind: "guest", ...g }));

      this.activeIndex = -1;
      if (!this.suggestions.length) {
        this.close();
        return;
      }
      this.open();
      this.render();
    }

    render() {
      this.listEl.innerHTML = "";
      this.suggestions.forEach((suggestion, index) => {
        const item = document.createElement("li");
        item.setAttribute("role", "option");
        item.id = `${this.listId}-opt-${index}`;
        const isActive = index === this.activeIndex;

        item.className =
          "invite-name-option" + (isActive ? " invite-name-option--active" : "");
        item.textContent = suggestion.name;

        item.setAttribute("aria-selected", isActive ? "true" : "false");
        if (isActive) {
          this.input.setAttribute("aria-activedescendant", item.id);
        }

        item.addEventListener("mousedown", (e) => {
          e.preventDefault();
          this.select(suggestion);
        });
        this.listEl.appendChild(item);
      });
    }

    select(suggestion) {
      this.input.value = suggestion.name;
      this.hiddenField.value = suggestion.id;
      this.selectedGuest = suggestion;
      this.input.dataset.userEdited = "true";
      this.helperText.textContent = "Existing guest - their stats will be preserved";
      this.helperText.hidden = false;
      this.close();
    }

    clearSelection() {
      this.selectedGuest = null;
      this.hiddenField.value = "";
      this.helperText.hidden = true;
    }

    open() {
      this.isOpen = true;
      this.listEl.hidden = false;
      this.input.setAttribute("aria-expanded", "true");
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
  }

  function initInviteNameCombobox() {
    const dataEl = document.getElementById("invite-guests-data");
    const input = document.getElementById("invite-player-name");
    const hiddenField = document.getElementById("invite-guest-player-id");

    if (!dataEl || !input || !hiddenField) return;

    let guests;
    try {
      guests = JSON.parse(dataEl.textContent);
    } catch (_) {
      return;
    }
    if (!Array.isArray(guests) || !guests.length) return;

    new InviteNameCombobox(input, hiddenField, guests);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initInviteNameCombobox);
  } else {
    initInviteNameCombobox();
  }
})();
