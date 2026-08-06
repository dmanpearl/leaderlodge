(function () {
  function loadLeaderboardCards() {
    const mount = document.getElementById("dashboard-leaderboard-cards");
    if (!mount) {
      return;
    }
    const url = mount.dataset.dashboardLeaderboardCardsUrl;
    if (!url) {
      return;
    }
    // No skeletons means there is nothing to fetch (empty state already shown).
    if (!mount.querySelector(".dashboard-leaderboard-skeletons")) {
      mount.removeAttribute("aria-busy");
      return;
    }

    fetch(url, {
      headers: { Accept: "text/html", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Leaderboard cards request failed");
        }
        return response.text();
      })
      .then((html) => {
        mount.innerHTML = html;
        mount.removeAttribute("aria-busy");
        if (typeof window.LeaderLodge !== "undefined") {
          window.LeaderLodge.initDashboardLeaderboardCollapses?.();
        }
      })
      .catch(() => {
        mount.removeAttribute("aria-busy");
        mount.innerHTML =
          '<div class="card"><div class="card-body"><p class="text-muted mb-0">Could not load leaderboards. Refresh to try again.</p></div></div>';
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadLeaderboardCards);
  } else {
    loadLeaderboardCards();
  }
})();
