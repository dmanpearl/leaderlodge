(function () {
  const FILTERS_STORAGE_KEY = "leaderlodge.askLodgeFiltersOpen";

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
      collapseId: "ask-lodge-filters-panel",
      iconId: "ask-lodge-filters-icon",
      storageKey: FILTERS_STORAGE_KEY,
      defaultOpen,
      onToggle(isOpen) {
        const summary = document.getElementById("ask-lodge-filters-summary");
        if (summary) {
          summary.hidden = isOpen;
        }
      },
    });
  }

  initFiltersCollapse();
})();
