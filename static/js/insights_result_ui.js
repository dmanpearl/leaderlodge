(function () {
  function copyIcon(copyBtn) {
    return copyBtn.querySelector(".insights-copy-icon");
  }

  function resetCopyIcon(copyBtn) {
    const icon = copyIcon(copyBtn);
    if (!icon) {
      return;
    }
    icon.className = "bi bi-clipboard insights-copy-icon";
    copyBtn.setAttribute("aria-label", "Copy answer");
    copyBtn.setAttribute("title", "Copy answer");
  }

  function showCopySuccess(copyBtn) {
    const icon = copyIcon(copyBtn);
    if (!icon) {
      return;
    }
    icon.className = "bi bi-check-lg insights-copy-icon";
    copyBtn.setAttribute("aria-label", "Copied");
    copyBtn.setAttribute("title", "Copied");
  }

  function bindCopyButton(copyBtn, getMarkdown) {
    if (!copyBtn || copyBtn.dataset.insightsCopyBound === "true") {
      return;
    }
    copyBtn.dataset.insightsCopyBound = "true";

    copyBtn.addEventListener("click", async function () {
      const markdown = getMarkdown();
      if (!markdown) {
        return;
      }
      try {
        await navigator.clipboard.writeText(markdown);
        showCopySuccess(copyBtn);
      } catch (_error) {
        resetCopyIcon(copyBtn);
      }
    });
  }

  function bindRefreshButton(refreshBtn, onRefresh) {
    if (!refreshBtn || refreshBtn.dataset.insightsRefreshBound === "true") {
      return;
    }
    refreshBtn.dataset.insightsRefreshBound = "true";
    refreshBtn.addEventListener("click", function () {
      onRefresh();
    });
  }

  function markStale(copyBtn) {
    resetCopyIcon(copyBtn);
  }

  function setResultActionsEnabled({ copyBtn, refreshBtn, enabled }) {
    if (copyBtn) {
      copyBtn.disabled = !enabled;
      if (!enabled) {
        resetCopyIcon(copyBtn);
      }
    }
    if (refreshBtn) {
      refreshBtn.disabled = !enabled;
    }
  }

  window.leaderlodgeInsightsResultUI = {
    bindCopyButton,
    bindRefreshButton,
    markStale,
    resetCopyIcon,
    setResultActionsEnabled,
  };
})();
