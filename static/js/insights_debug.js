(function () {
  const STORAGE_KEY = "leaderlodge.insightsDebugOpen";
  let sectionCounter = 0;

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

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function nextSectionId(prefix) {
    sectionCounter += 1;
    return `insights-debug-${prefix}-${sectionCounter}`;
  }

  function renderJsonBlock(data) {
    return `<pre class="insights-debug-json mb-0">${escapeHtml(
      JSON.stringify(data, null, 2)
    )}</pre>`;
  }

  function renderCollapsibleSection({ title, summary, bodyHtml, open = false }) {
    const sectionId = nextSectionId("section");
    const iconClass = open ? "bi-chevron-down" : "bi-chevron-right";
    return `
      <section class="insights-debug-section card mb-2">
        <div class="card-header py-2 px-2">
          <button
            class="btn btn-sm btn-link text-decoration-none text-body p-0 d-flex insights-debug-section-toggle w-100 text-start"
            type="button"
            data-bs-toggle="collapse"
            data-bs-target="#${sectionId}"
            aria-expanded="${open ? "true" : "false"}"
            aria-controls="${sectionId}"
          >
            <i class="bi ${iconClass} me-1 insights-debug-section-icon" aria-hidden="true"></i>
            <span class="fw-semibold">${escapeHtml(title)}</span>
            ${
              summary
                ? `<span class="text-muted ms-1 insights-debug-section-summary">(${escapeHtml(summary)})</span>`
                : ""
            }
          </button>
        </div>
        <div id="${sectionId}" class="collapse ${open ? "show" : ""}">
          <div class="card-body py-2 px-2">${bodyHtml}</div>
        </div>
      </section>
    `;
  }

  function bindSectionIcons(root) {
    root.querySelectorAll(".insights-debug-section .collapse").forEach((collapse) => {
      const button = root.querySelector(`[data-bs-target="#${collapse.id}"]`);
      const icon = button ? button.querySelector(".insights-debug-section-icon") : null;
      if (!button || !icon) {
        return;
      }
      collapse.addEventListener("shown.bs.collapse", () => {
        icon.classList.replace("bi-chevron-right", "bi-chevron-down");
      });
      collapse.addEventListener("hidden.bs.collapse", () => {
        icon.classList.replace("bi-chevron-down", "bi-chevron-right");
      });
    });
  }

  function summarizeToolArgs(tool, args) {
    if (!args || typeof args !== "object") {
      return "";
    }
    const parts = [];
    if (args.player_query) {
      parts.push(`player: ${args.player_query}`);
    }
    if (args.player_id !== undefined) {
      parts.push(`player_id: ${args.player_id}`);
    }
    if (args.game_type_code) {
      parts.push(`game: ${args.game_type_code}`);
    }
    if (args.placement !== undefined) {
      parts.push(`placement: ${args.placement}`);
    }
    if (args.month !== undefined) {
      parts.push(`month: ${args.month}`);
    }
    if (args.year !== undefined) {
      parts.push(`year: ${args.year}`);
    }
    if (args.metric) {
      parts.push(`metric: ${args.metric}`);
    }
    if (args.limit !== undefined) {
      parts.push(`limit: ${args.limit}`);
    }
    return parts.join(", ") || JSON.stringify(args);
  }

  function summarizeToolResult(tool, result) {
    if (!result || typeof result !== "object") {
      return "No result";
    }
    if (result.error) {
      return `Error: ${result.error}`;
    }
    if (tool === "list_game_types" && Array.isArray(result.game_types)) {
      return `${result.game_types.length} game type(s)`;
    }
    if (tool === "list_group_players" && Array.isArray(result.players)) {
      return `${result.players.length} player(s)`;
    }
    if (tool === "query_leaderboard" && Array.isArray(result.rankings)) {
      return `${result.rankings.length} ranking row(s)`;
    }
    if (tool === "query_placement_leaders" && Array.isArray(result.leaders)) {
      return `${result.leaders.length} leader row(s)`;
    }
    if (tool === "query_month_leaders" && Array.isArray(result.leaders)) {
      return `${result.leaders.length} leader row(s)`;
    }
    if (tool === "query_rank_trends" && Array.isArray(result.players)) {
      return `${result.players.length} trend row(s)`;
    }
    if (tool === "query_player_detail") {
      if (result.has_games === false) {
        return "No games for player";
      }
      const label = result.display_label || "Player";
      const games = result.games_played !== undefined ? `${result.games_played} games` : "";
      return games ? `${label}, ${games}` : label;
    }
    return "Result returned";
  }

  const APP_LANE_LABEL = "LL";

  function renderAppLane(tagName) {
    return `<${tagName} class="insights-debug-seq-lane insights-debug-seq-lane--app">${APP_LANE_LABEL}</${tagName}>`;
  }

  function renderSequenceHeader() {
    return `
      <div class="insights-debug-seq-step insights-debug-seq-step--header">
        ${renderAppLane("div")}
        <div class="insights-debug-seq-mid insights-debug-seq-mid--header">
          <span class="insights-debug-seq-header-label">Action</span>
        </div>
        <div class="insights-debug-seq-lane insights-debug-seq-lane--ai">AI</div>
      </div>
    `;
  }

  function renderSequenceStep({ label, direction }) {
    const actionLabel = String(label || "").trim();
    if (!actionLabel) {
      return "";
    }
    const arrow = direction === "app-to-ai" ? "→" : "←";
    return `
      <div class="insights-debug-seq-step">
        ${renderAppLane("div")}
        <div class="insights-debug-seq-mid">
          <span class="insights-debug-seq-arrow" aria-hidden="true">${arrow}</span>
          <span class="insights-debug-seq-label">${escapeHtml(actionLabel)}</span>
        </div>
        <div class="insights-debug-seq-lane insights-debug-seq-lane--ai">AI</div>
      </div>
    `;
  }

  function renderToolRoundDetails(round, index) {
    const calls = Array.isArray(round.calls) ? round.calls : [];
    const summary = calls.map((call) => call.tool).join(", ");

    const detailBlocks = calls
      .map((call) =>
        renderCollapsibleSection({
          title: call.tool,
          summary: summarizeToolResult(call.tool, call.result),
          open: false,
          bodyHtml: `
            <p class="text-muted mb-2">Request from AI to LeaderLodge</p>
            ${renderJsonBlock(call.arguments || {})}
            <p class="text-muted mb-2 mt-3">Response from LeaderLodge</p>
            ${renderJsonBlock(call.result || {})}
          `,
        })
      )
      .join("");

    return renderCollapsibleSection({
      title: `Round ${round.round || index + 1}`,
      summary: summary || "No tool calls",
      open: false,
      bodyHtml: detailBlocks || "<p class=\"text-muted mb-0\">No calls in this round.</p>",
    });
  }

  function renderAskSequenceOverview(debug) {
    const question = String(debug.question || "").trim();
    const toolRounds = Array.isArray(debug.tool_rounds) ? debug.tool_rounds : [];
    const steps = [];

    if (question) {
      steps.push(renderSequenceStep({ label: question, direction: "app-to-ai" }));
    }

    toolRounds.forEach((round) => {
      (round.calls || []).forEach((call) => {
        const argsSummary = summarizeToolArgs(call.tool, call.arguments);
        const toolLabel = `${call.tool}${argsSummary ? ` (${argsSummary})` : ""}`;
        steps.push(
          renderSequenceStep({
            label: toolLabel,
            direction: "ai-to-app",
          })
        );
        steps.push(
          renderSequenceStep({
            label: summarizeToolResult(call.tool, call.result),
            direction: "app-to-ai",
          })
        );
      });
    });

    if (debug.final_answer) {
      steps.push(
        renderSequenceStep({
          label: "Final answer",
          direction: "ai-to-app",
        })
      );
    }

    if (!steps.length) {
      return '<p class="text-muted mb-0">No actions recorded for this request.</p>';
    }

    return `${renderSequenceHeader()}${steps.join("")}`;
  }

  function renderAskDebug(debug) {
    const question = debug.question || "";
    const tools = Array.isArray(debug.available_tools) ? debug.available_tools : [];
    const toolRounds = Array.isArray(debug.tool_rounds) ? debug.tool_rounds : [];
    const toolsUsed = Array.isArray(debug.tools_used) ? debug.tools_used : [];
    const finalAnswer = debug.final_answer || "";

    const toolsList = tools
      .map(
        (tool) =>
          `<li><code>${escapeHtml(tool.name)}</code>: ${escapeHtml(tool.description)}</li>`
      )
      .join("");

    const sections = [
      renderCollapsibleSection({
        title: "1. Your question",
        summary: question.length > 60 ? `${question.slice(0, 57)}...` : question,
        open: true,
        bodyHtml: `<p class="mb-2">${escapeHtml(question)}</p>${renderCollapsibleSection(
          {
            title: "Full user message sent to AI",
            summary: "roster and scope included",
            open: false,
            bodyHtml: renderJsonBlock({
              question: debug.question,
              initial_user_message: debug.initial_user_message,
              scope: debug.scope,
              player_roster: debug.player_roster,
            }),
          }
        )}`,
      }),
      renderCollapsibleSection({
        title: "2. Tools offered to AI",
        summary: `${tools.length} tool(s)`,
        open: false,
        bodyHtml: `
          <p class="text-muted mb-2">LeaderLodge registers these tools with the model. The model chooses which to call.</p>
          <ul class="insights-debug-tool-list mb-2">${toolsList}</ul>
          ${renderCollapsibleSection({
            title: "Raw tool schemas",
            summary: "API format",
            open: false,
            bodyHtml: renderJsonBlock(tools),
          })}
        `,
      }),
      renderCollapsibleSection({
        title: "3. AI tool rounds",
        summary: toolsUsed.length
          ? `${toolRounds.length} round(s), ${toolsUsed.join(" → ")}`
          : "No tool calls",
        open: true,
        bodyHtml: `
          ${
            debug.note
              ? `<p class="text-muted mb-2">${escapeHtml(debug.note)}</p>`
              : ""
          }
          <div class="insights-debug-seq mb-3">${renderAskSequenceOverview(debug)}</div>
          ${toolRounds.map((round, index) => renderToolRoundDetails(round, index)).join("")}
        `,
      }),
      renderCollapsibleSection({
        title: "4. Final answer from AI",
        summary: finalAnswer.split("\n")[0].replace(/^#+\s*/, "").slice(0, 60),
        open: true,
        bodyHtml: `<pre class="insights-debug-answer mb-0">${escapeHtml(finalAnswer)}</pre>`,
      }),
      renderCollapsibleSection({
        title: "Raw debug payload",
        summary: "full JSON",
        open: false,
        bodyHtml: renderJsonBlock(debug),
      }),
    ];

    return `<div class="insights-debug-structured">${sections.join("")}</div>`;
  }

  function renderContextualDebug(debug) {
    const question =
      debug.question ||
      (debug.preset && debug.preset !== "custom" ? `Preset: ${debug.preset}` : "");
    const context = debug.context || {};
    const dataQuality = context.data_quality || {};
    const games =
      dataQuality.games_in_period ?? dataQuality.total_weighted_games ?? null;

    const sections = [
      renderCollapsibleSection({
        title: "1. Your question",
        summary: question || debug.preset || "Preset insight",
        open: true,
        bodyHtml: `<p class="mb-0">${escapeHtml(question || debug.preset || "")}</p>`,
      }),
      renderCollapsibleSection({
        title: "2. Context snapshot sent to AI",
        summary: games !== null ? `${games} weighted game(s)` : context.scope || debug.mode,
        open: false,
        bodyHtml: renderJsonBlock(context),
      }),
      renderCollapsibleSection({
        title: "3. Prompt sent to AI",
        summary: "system + user message",
        open: false,
        bodyHtml: `
          <p class="text-muted mb-2">System prompt</p>
          <pre class="insights-debug-answer mb-2">${escapeHtml(debug.system_prompt || "")}</pre>
          <p class="text-muted mb-2">User message</p>
          <pre class="insights-debug-answer mb-0">${escapeHtml(debug.user_message || "")}</pre>
        `,
      }),
      renderCollapsibleSection({
        title: "4. Final answer from AI",
        summary: "shown above in the panel",
        open: false,
        bodyHtml: `<p class="text-muted mb-0">The rendered answer appears in the main Insights result area.</p>`,
      }),
      renderCollapsibleSection({
        title: "Raw debug payload",
        summary: "full JSON",
        open: false,
        bodyHtml: renderJsonBlock(debug),
      }),
    ];

    return `<div class="insights-debug-structured">${sections.join("")}</div>`;
  }

  function renderStructuredDebug(debug) {
    if (!debug || typeof debug !== "object") {
      return '<p class="text-muted mb-0">No debug payload returned.</p>';
    }
    if (debug.mode === "ask") {
      return renderAskDebug(debug);
    }
    return renderContextualDebug(debug);
  }

  function render(panelOrRoot, debugData) {
    const root = findRoot(panelOrRoot);
    if (!root) {
      return;
    }
    const view = root.querySelector(".insights-debug-view");
    if (!view) {
      return;
    }
    view.innerHTML = renderStructuredDebug(debugData);
    bindSectionIcons(root);
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
