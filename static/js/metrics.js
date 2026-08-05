(function () {
  function initCollapseSection({
    collapseId,
    iconId,
    storageKey,
    defaultOpen = true,
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

  function initSection({ collapseId, iconId, storageKey, summaryId }) {
    initCollapseSection({
      collapseId,
      iconId,
      storageKey,
      defaultOpen: true,
      onToggle(isOpen) {
        const summary = document.getElementById(summaryId);
        if (summary) {
          summary.hidden = isOpen;
        }
      },
    });
  }

  initSection({
    collapseId: "metrics-groups-panel",
    iconId: "metrics-groups-icon",
    storageKey: "leaderlodge.metricsGroupsOpen",
    summaryId: "metrics-groups-summary",
  });
  initSection({
    collapseId: "metrics-games-panel",
    iconId: "metrics-games-icon",
    storageKey: "leaderlodge.metricsGamesOpen",
    summaryId: "metrics-games-summary",
  });
})();
