(function () {
  const FILTERS_STORAGE_KEY = "leaderlodge.leaderboardFiltersOpen";

  function initCollapseSection({
    collapseId,
    iconId,
    storageKey,
    defaultOpen = false,
    onToggle,
  }) {
    const collapse = document.getElementById(collapseId);
    if (!collapse) {
      return;
    }

    const stored = window.sessionStorage.getItem(storageKey);
    const shouldOpen = stored === null ? defaultOpen : stored === "true";
    const instance = bootstrap.Collapse.getOrCreateInstance(collapse, {
      toggle: false,
    });

    if (shouldOpen) {
      instance.show();
    } else {
      instance.hide();
    }

    collapse.addEventListener("shown.bs.collapse", () => {
      window.sessionStorage.setItem(storageKey, "true");
      updateCollapseIcon(iconId, true);
      onToggle?.(true);
    });
    collapse.addEventListener("hidden.bs.collapse", () => {
      window.sessionStorage.setItem(storageKey, "false");
      updateCollapseIcon(iconId, false);
      onToggle?.(false);
    });

    updateCollapseIcon(iconId, shouldOpen);
    onToggle?.(shouldOpen);
  }

  function updateCollapseIcon(iconId, isOpen) {
    const icon = document.getElementById(iconId);
    if (!icon) {
      return;
    }
    icon.classList.toggle("bi-chevron-down", isOpen);
    icon.classList.toggle("bi-chevron-right", !isOpen);
  }

  function initFiltersCollapse() {
    const defaultOpen = window.matchMedia("(min-width: 768px)").matches;

    initCollapseSection({
      collapseId: "leaderboard-filters-panel",
      iconId: "leaderboard-filters-icon",
      storageKey: FILTERS_STORAGE_KEY,
      defaultOpen,
      onToggle(isOpen) {
        const summary = document.getElementById("leaderboard-filters-summary");
        if (summary) {
          summary.hidden = isOpen;
        }
      },
    });
  }

  function syncGameTypeIcon() {
    const select = document.getElementById("game-type-select");
    const icon = document.getElementById("leaderboard-game-type-icon");
    const wrap = document.querySelector(".leaderboard-game-type-wrap");
    if (!select || !icon || !wrap) {
      return;
    }

    const option = select.options[select.selectedIndex];
    const iconUrl = option?.dataset.iconUrl;
    if (iconUrl) {
      icon.src = iconUrl;
      icon.classList.remove("d-none");
      wrap.classList.add("leaderboard-game-type-wrap--has-icon");
      return;
    }

    icon.removeAttribute("src");
    icon.classList.add("d-none");
    wrap.classList.remove("leaderboard-game-type-wrap--has-icon");
  }

  function initGameTypeIcon() {
    const select = document.getElementById("game-type-select");
    if (!select) {
      return;
    }

    syncGameTypeIcon();
    select.addEventListener("change", syncGameTypeIcon);
  }

  initFiltersCollapse();
  initGameTypeIcon();
})();
