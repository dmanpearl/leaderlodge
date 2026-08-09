(function () {
  const BAR_ID = "nav-pending-bar";

  function bar() {
    return document.getElementById(BAR_ID);
  }

  function show() {
    const el = bar();
    if (!el) {
      return;
    }
    el.classList.add("is-active");
    el.removeAttribute("hidden");
  }

  function hide() {
    const el = bar();
    if (!el) {
      return;
    }
    el.classList.remove("is-active");
    el.setAttribute("hidden", "");
  }

  function shouldIgnoreAnchor(anchor, event) {
    if (!anchor || !anchor.getAttribute("href")) {
      return true;
    }
    if (event.defaultPrevented) {
      return true;
    }
    if (event.button !== 0) {
      return true;
    }
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return true;
    }
    if (anchor.target && anchor.target !== "_self") {
      return true;
    }
    if (anchor.hasAttribute("download")) {
      return true;
    }

    let url;
    try {
      url = new URL(anchor.href, window.location.href);
    } catch (_err) {
      return true;
    }
    if (url.protocol === "javascript:") {
      return true;
    }
    if (url.origin !== window.location.origin) {
      return true;
    }
    if (
      url.pathname === window.location.pathname &&
      url.search === window.location.search &&
      url.hash
    ) {
      return true;
    }
    return false;
  }

  function shouldIgnoreDataHrefClick(event) {
    if (event.defaultPrevented) {
      return true;
    }
    if (event.button !== 0) {
      return true;
    }
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return true;
    }
    // Nested controls keep their own behavior (group links, header links, etc.).
    if (
      event.target.closest("a[href], button, input, select, textarea, label")
    ) {
      return true;
    }
    return false;
  }

  function dataHrefRowFromEvent(event) {
    const row = event.target.closest("[data-href]");
    if (!row || row.tagName === "A") {
      return null;
    }
    const href = row.getAttribute("data-href");
    if (!href) {
      return null;
    }
    return row;
  }

  document.addEventListener(
    "click",
    function (event) {
      const anchor = event.target.closest("a[href]");
      if (!anchor || shouldIgnoreAnchor(anchor, event)) {
        return;
      }
      show();
    },
    true
  );

  // Whole-row navigations (game list, dashboard, leaderboard, etc.).
  // Bubble phase so nested stopPropagation (row action menus) still wins.
  // Lives here so it still works if a page script fails during init.
  document.addEventListener("click", function (event) {
    if (shouldIgnoreDataHrefClick(event)) {
      return;
    }
    const row = dataHrefRowFromEvent(event);
    if (!row) {
      return;
    }
    navigate(row.getAttribute("data-href"));
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    const row = event.target.closest("[data-href]");
    if (!row || row !== event.target || row.tagName === "A") {
      return;
    }
    const href = row.getAttribute("data-href");
    if (!href) {
      return;
    }
    event.preventDefault();
    navigate(href);
  });

  window.addEventListener("pageshow", function () {
    hide();
  });

  function navigate(url) {
    show();
    window.location = url;
  }

  window.LeaderLodge = window.LeaderLodge || {};
  window.LeaderLodge.showNavPending = show;
  window.LeaderLodge.hideNavPending = hide;
  window.LeaderLodge.navigate = navigate;
})();
