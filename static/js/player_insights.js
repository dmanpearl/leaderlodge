(function () {
  const panel = document.getElementById("player-insights-panel");
  if (!panel) {
    return;
  }

  const generateBtn = document.getElementById("player-insights-generate");
  const copyBtn = document.getElementById("player-insights-copy");
  const regenerateBtn = document.getElementById("player-insights-regenerate");
  const modelSelect = document.getElementById("player-insights-model");
  const customWrap = document.getElementById("player-insights-custom-wrap");
  const questionInput = document.getElementById("player-insights-question");
  const statusEl = document.getElementById("player-insights-status");
  const errorEl = document.getElementById("player-insights-error");
  const resultEl = document.getElementById("player-insights-result");
  const presetInputs = document.querySelectorAll('input[name="player-insights-preset"]');

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
    const checked = document.querySelector('input[name="player-insights-preset"]:checked');
    return checked ? checked.value : "strengths";
  }

  function updateCustomVisibility() {
    const isCustom = selectedPreset() === "custom";
    customWrap.classList.toggle("d-none", !isCustom);
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
    if (meta && meta.games_in_period !== undefined) {
      const modelLabel = meta.model_label || meta.model || "";
      statusEl.textContent = `Based on ${meta.games_in_period} weighted game(s)${modelLabel ? ` · ${modelLabel}` : ""}${meta.cached ? " · cached" : ""}.`;
    }
  }

  function buildPayload() {
    const payload = {
      group_id: panel.dataset.groupId,
      player_id: panel.dataset.playerId,
      game_type_code: panel.dataset.gameTypeCode,
      preset: selectedPreset(),
      model: modelSelect.value,
      question: "",
      refresh: isRegenerate,
    };
    if (panel.dataset.year) {
      payload.year = panel.dataset.year;
    }
    if (panel.dataset.month) {
      payload.month = panel.dataset.month;
    }
    if (payload.preset === "custom") {
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
})();
