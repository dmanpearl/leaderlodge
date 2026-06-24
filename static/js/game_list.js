(function () {
  const STORAGE_KEY = "leaderlodge.gameListStatsOpen";

  function initStatsCollapse() {
    const collapse = document.getElementById("game-list-stats");
    if (!collapse) {
      return;
    }

    const stored = window.sessionStorage.getItem(STORAGE_KEY);
    const shouldOpen = stored === null ? false : stored === "true";
    const instance = bootstrap.Collapse.getOrCreateInstance(collapse, {
      toggle: false,
    });

    if (shouldOpen) {
      instance.show();
    } else {
      instance.hide();
    }

    collapse.addEventListener("shown.bs.collapse", () => {
      window.sessionStorage.setItem(STORAGE_KEY, "true");
      updateToggleIcon(true);
    });
    collapse.addEventListener("hidden.bs.collapse", () => {
      window.sessionStorage.setItem(STORAGE_KEY, "false");
      updateToggleIcon(false);
    });

    updateToggleIcon(shouldOpen);
  }

  function updateToggleIcon(isOpen) {
    const icon = document.getElementById("game-list-stats-icon");
    if (!icon) {
      return;
    }
    icon.classList.toggle("bi-chevron-down", isOpen);
    icon.classList.toggle("bi-chevron-right", !isOpen);
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
      select.style.width = `${Math.ceil(measurer.getBoundingClientRect().width) + 4}px`;
    }

    resizeTitleSelect();
    select.addEventListener("change", resizeTitleSelect);
    window.addEventListener("resize", resizeTitleSelect);
  }

  function init() {
    initStatsCollapse();
    initTitleSelect();
    updateFooterHeader();
    window.addEventListener("resize", updateFooterHeader);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
