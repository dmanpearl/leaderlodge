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
    icon.classList.toggle("bi-chevron-up", isOpen);
    icon.classList.toggle("bi-chevron-down", !isOpen);
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

  function init() {
    initStatsCollapse();
    updateFooterHeader();
    window.addEventListener("resize", updateFooterHeader);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
