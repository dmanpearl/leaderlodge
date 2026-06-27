(function () {
  document.querySelectorAll(".player-insights-offcanvas[data-insights-scope]").forEach((panel) => {
    const generateBtn = panel.querySelector(".insights-generate-btn");
    const copyBtn = panel.querySelector(".insights-copy-btn");
    const regenerateBtn = panel.querySelector(".insights-regenerate-btn");
    const modelSelect = panel.querySelector(".insights-model-select");
    const customWrap = panel.querySelector(".insights-custom-wrap");
    const questionInput = panel.querySelector(".insights-question-input");
    const statusEl = panel.querySelector(".insights-status");
    const errorEl = panel.querySelector(".insights-error");
    const resultEl = panel.querySelector(".insights-result");
    const presetInputs = panel.querySelectorAll(".insights-preset-input");

    if (!generateBtn || !panel.dataset.insightsUrl) {
      return;
    }

    let lastMarkdown = "";
    let isRegenerate = false;

    function csrfToken() {
      return (
        (window.leaderlodgeGetCsrfToken && window.leaderlodgeGetCsrfToken()) ||
        (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ||
        ""
      );
    }

    function selectedPreset() {
      const checked = panel.querySelector(".insights-preset-input:checked");
      return checked ? checked.value : "overview";
    }

    function updateCustomVisibility() {
      const isCustom = selectedPreset() === "custom";
      if (customWrap) {
        customWrap.classList.toggle("d-none", !isCustom);
      }
    }

    function setLoading(isLoading) {
      generateBtn.disabled = isLoading;
      regenerateBtn.disabled = isLoading || !lastMarkdown;
      copyBtn.disabled = isLoading || !lastMarkdown;
      modelSelect.disabled = isLoading;
      presetInputs.forEach((input) => {
        input.disabled = isLoading;
      });
      if (questionInput) {
        questionInput.disabled = isLoading;
      }
      statusEl.textContent = isLoading ? "Analyzing..." : "";
    }

    function showError(message) {
      errorEl.textContent = message;
      errorEl.classList.remove("d-none");
    }

    function clearError() {
      errorEl.textContent = "";
      errorEl.classList.add("d-none");
    }

    function renderResult(html, meta) {
      resultEl.innerHTML = `<div class="player-insights-markdown">${html}</div>`;
      if (meta) {
        const modelLabel = meta.model_label || meta.model || "";
        const basis = meta.games_in_period !== undefined ? `${meta.games_in_period} weighted game(s)` : "group stats";
        statusEl.textContent = `Based on ${basis}${modelLabel ? ` · ${modelLabel}` : ""}${meta.cached ? " · cached" : ""}.`;
      }
    }

    function buildPayload() {
      const payload = {
        group_id: panel.dataset.groupId,
        scope: panel.dataset.insightsScope,
        preset: selectedPreset(),
        model: modelSelect.value,
        question: "",
        refresh: isRegenerate,
      };
      if (panel.dataset.gameTypeCode) {
        payload.game_type_code = panel.dataset.gameTypeCode;
      }
      if (panel.dataset.year) {
        payload.year = panel.dataset.year;
      }
      if (panel.dataset.month) {
        payload.month = panel.dataset.month;
      }
      if (panel.dataset.granularity) {
        payload.granularity = panel.dataset.granularity;
      }
      if (payload.preset === "custom" && questionInput) {
        payload.question = questionInput.value.trim();
      }
      return payload;
    }

    async function requestInsight() {
      clearError();
      setLoading(true);
      try {
        const response = await fetch(panel.dataset.insightsUrl, {
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
          showError(data.error || "Could not generate insight.");
          return;
        }
        lastMarkdown = data.markdown || "";
        renderResult(data.html || "", data.meta || {});
        copyBtn.disabled = !lastMarkdown;
        regenerateBtn.disabled = !lastMarkdown;
      } catch (_error) {
        showError("Could not generate insight. Please try again.");
      } finally {
        isRegenerate = false;
        setLoading(false);
      }
    }

    presetInputs.forEach((input) => {
      input.addEventListener("change", updateCustomVisibility);
    });

    generateBtn.addEventListener("click", function () {
      isRegenerate = false;
      requestInsight();
    });
    regenerateBtn.addEventListener("click", function () {
      isRegenerate = true;
      requestInsight();
    });

    copyBtn.addEventListener("click", async function () {
      if (!lastMarkdown) {
        return;
      }
      try {
        await navigator.clipboard.writeText(lastMarkdown);
        statusEl.textContent = "Copied to clipboard.";
      } catch (_error) {
        statusEl.textContent = "Could not copy to clipboard.";
      }
    });

    updateCustomVisibility();
  });
})();
