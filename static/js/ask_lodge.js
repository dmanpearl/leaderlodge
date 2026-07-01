(function () {
  const panel = document.querySelector(".ask-lodge-panel[data-ask-url]");
  if (!panel) {
    return;
  }

  if (window.leaderlodgeInsightsDebug) {
    window.leaderlodgeInsightsDebug.init(panel);
  }

  const submitBtn = panel.querySelector(".ask-lodge-submit-btn");
  const resultWrap = panel.querySelector(".insights-result-wrap");
  const copyBtn = resultWrap ? resultWrap.querySelector(".insights-copy-btn") : null;
  const refreshBtn = resultWrap ? resultWrap.querySelector(".insights-refresh-btn") : null;
  const modelSelect = panel.querySelector(".insights-model-select");
  const questionInput = panel.querySelector(".insights-question-input");
  const progressEl = panel.querySelector(".insights-progress");
  const statusEl = panel.querySelector(".insights-status");
  const errorEl = panel.querySelector(".insights-error");
  const resultEl = panel.querySelector(".insights-result");
  const resultUI = window.leaderlodgeInsightsResultUI;

  if (!resultEl || !copyBtn || !refreshBtn || !resultUI) {
    return;
  }

  let lastMarkdown = "";
  let isRegenerate = false;
  let loading = false;

  function csrfToken() {
    return (
      (window.leaderlodgeGetCsrfToken && window.leaderlodgeGetCsrfToken()) ||
      (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ||
      ""
    );
  }

  function markResultStale() {
    resultUI.markStale(copyBtn);
  }

  function setLoading(isLoading) {
    loading = isLoading;
    resultUI.setResultActionsEnabled({
      copyBtn,
      refreshBtn,
      enabled: !isLoading && Boolean(lastMarkdown),
    });
    if (modelSelect) {
      modelSelect.disabled = isLoading;
    }
    if (questionInput) {
      questionInput.disabled = isLoading;
    }
    if (submitBtn) {
      submitBtn.disabled = isLoading;
    }
    if (progressEl) {
      progressEl.classList.toggle("d-none", !isLoading);
      progressEl.classList.toggle("d-flex", isLoading);
    }
    panel.setAttribute("aria-busy", isLoading ? "true" : "false");
    if (isLoading) {
      statusEl.textContent = "";
      markResultStale();
    }
  }

  function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.remove("d-none");
  }

  function clearError() {
    errorEl.textContent = "";
    errorEl.classList.add("d-none");
  }

  function formatStatusMeta(meta) {
    if (!meta) {
      return "";
    }
    const modelLabel = meta.model_label || meta.model || "";
    const cachedSuffix = meta.cached ? " · cached" : "";
    const toolsSuffix =
      meta.tools_used && meta.tools_used.length
        ? ` · tools: ${meta.tools_used.join(", ")}`
        : "";
    return `Ask the Lodge${modelLabel ? ` · ${modelLabel}` : ""}${toolsSuffix}${cachedSuffix}.`;
  }

  function buildPayload() {
    const payload = {
      group_id: panel.dataset.groupId,
      game_type_code: panel.dataset.gameTypeCode || "",
      question: questionInput ? questionInput.value.trim() : "",
      model: modelSelect ? modelSelect.value : "",
      refresh: isRegenerate,
    };
    if (panel.dataset.year) {
      payload.year = panel.dataset.year;
    }
    if (panel.dataset.month) {
      payload.month = panel.dataset.month;
    }
    if (
      window.leaderlodgeInsightsDebug &&
      window.leaderlodgeInsightsDebug.isEnabled(panel)
    ) {
      payload.include_debug = true;
    }
    return payload;
  }

  async function requestAnswer() {
    if (loading) {
      return;
    }
    const question = questionInput ? questionInput.value.trim() : "";
    if (!question) {
      showError("Enter a question first.");
      if (questionInput) {
        questionInput.focus();
      }
      return;
    }

    clearError();
    setLoading(true);
    try {
      const response = await fetch(panel.dataset.askUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        credentials: "same-origin",
        body: JSON.stringify(buildPayload()),
      });
      const data = await response.json();
      if (!response.ok) {
        showError(data.error || "Could not answer that question.");
        return;
      }
      lastMarkdown = data.markdown || "";
      resultEl.innerHTML = `<div class="player-insights-markdown">${data.html || ""}</div>`;
      statusEl.textContent = formatStatusMeta(data.meta || {});
      if (window.leaderlodgeInsightsDebug) {
        window.leaderlodgeInsightsDebug.render(panel, data.debug);
      }
      resultUI.resetCopyIcon(copyBtn);
      resultUI.setResultActionsEnabled({
        copyBtn,
        refreshBtn,
        enabled: Boolean(lastMarkdown),
      });
    } catch (_error) {
      showError("Could not answer that question. Please try again.");
    } finally {
      isRegenerate = false;
      setLoading(false);
    }
  }

  resultUI.bindCopyButton(copyBtn, () => lastMarkdown);
  resultUI.bindRefreshButton(refreshBtn, function () {
    isRegenerate = true;
    requestAnswer();
  });

  if (submitBtn) {
    submitBtn.addEventListener("click", function () {
      isRegenerate = false;
      requestAnswer();
    });
  }

  if (questionInput) {
    questionInput.addEventListener("input", markResultStale);
    questionInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        isRegenerate = false;
        requestAnswer();
      }
    });
  }

  if (modelSelect) {
    modelSelect.addEventListener("change", markResultStale);
  }
})();
