/**
 * Keep style / score-type icons in sync with their select value.
 */
(function () {
  function syncIcon(select) {
    if (!select) {
      return;
    }
    const wrap = select.closest("[data-score-type-wrap]");
    let icon = wrap
      ? wrap.querySelector("[data-score-type-icon]")
      : document.querySelector(
          `[data-score-type-filter-icon][data-for-select="${select.id}"]`
        );
    if (!icon) {
      icon = document.querySelector("[data-score-type-icon]");
    }
    if (!icon) {
      return;
    }
    const selected = select.options[select.selectedIndex];
    const url = (selected && selected.getAttribute("data-icon-url")) || "";
    if (url) {
      icon.src = url;
      icon.classList.remove("d-none");
    } else {
      icon.removeAttribute("src");
      icon.classList.add("d-none");
    }
  }

  function bindSelect(select) {
    if (!select || select.dataset.scoreTypeIconBound === "1") {
      return;
    }
    select.dataset.scoreTypeIconBound = "1";
    select.addEventListener("change", function () {
      syncIcon(select);
    });
    syncIcon(select);
  }

  function init() {
    document
      .querySelectorAll("[data-score-type-select], [data-score-type-filter-select]")
      .forEach(bindSelect);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.LeaderLodgeScoreTypeSelect = { syncIcon: syncIcon, init: init };
})();
