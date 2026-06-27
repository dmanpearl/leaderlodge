(function () {
  document.querySelectorAll(".player-insights-offcanvas[data-insights-url]").forEach((panel) => {
    const copyBtn = panel.querySelector(".insights-copy-btn");
    const regenerateBtn = panel.querySelector(".insights-regenerate-btn");
    const askGenerateBtn = panel.querySelector(".insights-ask-generate-btn");
    const modelSelect = panel.querySelector(".insights-model-select");
    const customWrap = panel.querySelector(".insights-custom-wrap");
    const questionInput = panel.querySelector(".insights-question-input");
    const progressEl = panel.querySelector(".insights-progress");
    const statusEl = panel.querySelector(".insights-status");
    const errorEl = panel.querySelector(".insights-error");
    const resultEl = panel.querySelector(".insights-result");
    const presetInputs = panel.querySelectorAll(".insights-preset-input");

    if (!panel.dataset.insightsUrl || !copyBtn || !regenerateBtn) {
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

    function selectedPreset() {
      const checked = panel.querySelector(".insights-preset-input:checked");
      return checked ? checked.value : "custom";
    }

    function updateCustomVisibility() {
      const isCustom = selectedPreset() === "custom";
      if (customWrap) {
        customWrap.classList.toggle("d-none", !isCustom);
      }
    }

    function setLoading(isLoading) {
      loading = isLoading;
      regenerateBtn.disabled = isLoading || !lastMarkdown;
      copyBtn.disabled = isLoading || !lastMarkdown;
      if (modelSelect) {
        modelSelect.disabled = isLoading;
      }
      presetInputs.forEach((input) => {
        input.disabled = isLoading;
      });
      if (questionInput) {
        questionInput.disabled = isLoading;
      }
      if (askGenerateBtn) {
        askGenerateBtn.disabled = isLoading;
      }
      if (progressEl) {
        progressEl.classList.toggle("d-none", !isLoading);
        progressEl.classList.toggle("d-flex", isLoading);
      }
      panel.setAttribute("aria-busy", isLoading ? "true" : "false");
      if (isLoading) {
        statusEl.textContent = "";
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

      if (panel.dataset.gameId) {
        return `Matchup insight${modelLabel ? ` · ${modelLabel}` : ""}${cachedSuffix}.`;
      }
      if (panel.dataset.insightsScope && panel.dataset.insightsScope !== "matchup") {
        const basis =
          meta.games_in_period !== undefined
            ? `${meta.games_in_period} weighted game(s)`
            : "group stats";
        return `Based on ${basis}${modelLabel ? ` · ${modelLabel}` : ""}${cachedSuffix}.`;
      }
      if (meta.games_in_period !== undefined) {
        return `Based on ${meta.games_in_period} weighted game(s)${modelLabel ? ` · ${modelLabel}` : ""}${cachedSuffix}.`;
      }
      return modelLabel ? `${modelLabel}${cachedSuffix}.` : "";
    }

    function renderResult(html, meta) {
      resultEl.innerHTML = `<div class="player-insights-markdown">${html}</div>`;
      statusEl.textContent = formatStatusMeta(meta);
    }

    function buildPayload() {
      const preset = selectedPreset();
      const payload = {
        preset,
        model: modelSelect ? modelSelect.value : "",
        question: "",
        refresh: isRegenerate,
      };

      if (panel.dataset.gameId) {
        payload.game_id = panel.dataset.gameId;
      } else if (panel.dataset.playerId) {
        payload.group_id = panel.dataset.groupId;
        payload.player_id = panel.dataset.playerId;
        payload.game_type_code = panel.dataset.gameTypeCode;
        if (panel.dataset.year) {
          payload.year = panel.dataset.year;
        }
        if (panel.dataset.month) {
          payload.month = panel.dataset.month;
        }
      } else {
        payload.group_id = panel.dataset.groupId;
        payload.scope = panel.dataset.insightsScope;
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
      }

      if (preset === "custom" && questionInput) {
        payload.question = questionInput.value.trim();
      }
      return payload;
    }

    async function requestInsight() {
      if (loading) {
        return;
      }
      if (selectedPreset() === "custom") {
        const question = questionInput ? questionInput.value.trim() : "";
        if (!question) {
          showError("Enter a question first.");
          if (questionInput) {
            questionInput.focus();
          }
          return;
        }
      }

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

    function triggerPresetGenerate() {
      isRegenerate = false;
      requestInsight();
    }

    presetInputs.forEach((input) => {
      input.addEventListener("change", function () {
        updateCustomVisibility();
      });
      input.addEventListener("click", function () {
        queueMicrotask(() => {
          if (input.checked && input.value !== "custom") {
            triggerPresetGenerate();
          }
        });
      });
    });

    if (askGenerateBtn) {
      askGenerateBtn.addEventListener("click", function () {
        isRegenerate = false;
        requestInsight();
      });
    }

    if (questionInput) {
      questionInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && selectedPreset() === "custom") {
          event.preventDefault();
          isRegenerate = false;
          requestInsight();
        }
      });
    }

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
