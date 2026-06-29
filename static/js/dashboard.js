(function () {
  const RECENT_GAMES_STORAGE_KEY = "leaderlodge.dashboardRecentGamesOpen";

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

  function initRecentGamesCollapse() {
    initCollapseSection({
      collapseId: "dashboard-recent-games",
      iconId: "dashboard-recent-games-icon",
      storageKey: RECENT_GAMES_STORAGE_KEY,
      defaultOpen: true,
      onToggle(isOpen) {
        const summary = document.getElementById("dashboard-recent-games-summary");
        if (summary) {
          summary.hidden = isOpen;
        }
      },
    });
  }

  initRecentGamesCollapse();
})();
