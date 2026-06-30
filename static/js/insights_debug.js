(function () {
  const STORAGE_KEY = "leaderlodge.insightsDebugOpen";

  function findRoot(panelOrRoot) {
    if (!panelOrRoot) {
      return null;
    }
    if (panelOrRoot.classList.contains("insights-debug-wrap")) {
      return panelOrRoot;
    }
    return panelOrRoot.querySelector(".insights-debug-wrap");
  }

  function isEnabled(panelOrRoot) {
    const root = findRoot(panelOrRoot);
    const toggle = root ? root.querySelector(".insights-debug-toggle") : null;
    return Boolean(toggle && toggle.checked);
  }

  function setPanelVisible(root, isOpen) {
    const panel = root.querySelector(".insights-debug-panel");
    if (panel) {
      panel.classList.toggle("d-none", !isOpen);
    }
  }

  function render(panelOrRoot, debugData) {
    const root = findRoot(panelOrRoot);
    if (!root) {
      return;
    }
    const pre = root.querySelector(".insights-debug-json");
    if (!pre) {
      return;
    }
    if (!debugData) {
      pre.textContent = "No debug payload returned.";
      return;
    }
    pre.textContent = JSON.stringify(debugData, null, 2);
    if (isEnabled(panelOrRoot)) {
      setPanelVisible(root, true);
    }
  }

  function init(panelOrRoot) {
    const root = findRoot(panelOrRoot);
    if (!root) {
      return;
    }
    const toggle = root.querySelector(".insights-debug-toggle");
    if (!toggle || toggle.dataset.insightsDebugInit === "true") {
      return;
    }
    toggle.dataset.insightsDebugInit = "true";

    const stored = window.sessionStorage.getItem(STORAGE_KEY);
    const shouldOpen = stored === "true";
    toggle.checked = shouldOpen;
    setPanelVisible(root, shouldOpen);

    toggle.addEventListener("change", () => {
      const isOpen = toggle.checked;
      window.sessionStorage.setItem(STORAGE_KEY, isOpen ? "true" : "false");
      setPanelVisible(root, isOpen);
    });
  }

  window.leaderlodgeInsightsDebug = {
    init,
    isEnabled,
    render,
  };
})();
