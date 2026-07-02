(function () {
  const STATS_STORAGE_KEY = "leaderlodge.gameListStatsOpen";
  const TYPE_STORAGE_KEY = "leaderlodge.gameListTypeOpen";

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

  function initStatsCollapse() {
    initCollapseSection({
      collapseId: "game-list-stats",
      iconId: "game-list-stats-icon",
      storageKey: STATS_STORAGE_KEY,
      defaultOpen: false,
    });
  }

  function initTypeFiltersCollapse() {
    const defaultOpen = window.matchMedia("(min-width: 768px)").matches;

    initCollapseSection({
      collapseId: "game-list-type-filters",
      iconId: "game-list-type-icon",
      storageKey: TYPE_STORAGE_KEY,
      defaultOpen,
      onToggle(isOpen) {
        const summary = document.getElementById("game-list-filters-summary");
        if (summary) {
          summary.hidden = isOpen;
        }
      },
    });
  }

  function updateFooterHeader() {
    const table = document.querySelector(".game-list-table");
    const footer = document.querySelector(".game-list-table-foot");
    if (!table || !footer) {
      return;
    }

    const tbody = table.querySelector("tbody");
    if (!tbody || tbody.rows.length === 0) {
      footer.classList.add("d-none");
      return;
    }

    const tableTop = table.getBoundingClientRect().top;
    const availableHeight = window.innerHeight - tableTop;
    const overflowsViewport = table.offsetHeight > availableHeight;

    footer.classList.toggle("d-none", !overflowsViewport);
  }

  function syncTitleIcon() {
    const select = document.getElementById("filter-game-type");
    const icon = document.getElementById("game-list-title-icon");
    const wrap = document.querySelector(".game-list-title-wrap");
    if (!select || !icon || !wrap) {
      return;
    }

    const option = select.options[select.selectedIndex];
    const iconUrl = option?.dataset.iconUrl;
    if (iconUrl) {
      icon.src = iconUrl;
      icon.classList.remove("d-none");
      wrap.classList.add("game-list-title-wrap--has-icon");
      return;
    }

    icon.removeAttribute("src");
    icon.classList.add("d-none");
    wrap.classList.remove("game-list-title-wrap--has-icon");
  }

  function initTitleSelect() {
    const select = document.getElementById("filter-game-type");
    if (!select) {
      return;
    }

    const measurer = document.createElement("span");
    measurer.setAttribute("aria-hidden", "true");
    measurer.style.cssText =
      "position:absolute;visibility:hidden;white-space:nowrap;pointer-events:none;";
    document.body.appendChild(measurer);

    function resizeTitleSelect() {
      const option = select.options[select.selectedIndex];
      if (!option) {
        return;
      }

      const style = window.getComputedStyle(select);
      measurer.style.font = style.font;
      measurer.style.letterSpacing = style.letterSpacing;
      measurer.textContent = option.text;
      // Select boxes clip the last glyph when width matches text exactly.
      let extra = 10;
      if (option.value === "progressiverummy") {
        extra += 3;
      }
      select.style.width = `${Math.ceil(measurer.getBoundingClientRect().width) + extra}px`;
    }

    syncTitleIcon();
    resizeTitleSelect();
    select.addEventListener("change", () => {
      syncTitleIcon();
      resizeTitleSelect();
    });
    window.addEventListener("resize", resizeTitleSelect);
  }

  function initRowNavigation() {
    document.querySelectorAll(".game-list-row[data-href]").forEach((row) => {
      const navigate = () => {
        window.location = row.dataset.href;
      };

      row.addEventListener("click", (event) => {
        if (event.target.closest("a")) {
          return;
        }
        navigate();
      });
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          navigate();
        }
      });
    });
  }

  function init() {
    initStatsCollapse();
    initTypeFiltersCollapse();
    initTitleSelect();
    initRowNavigation();
    updateFooterHeader();
    window.addEventListener("resize", updateFooterHeader);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
