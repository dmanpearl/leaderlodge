/**
 * Wires up [data-roster-invite] trigger buttons (roster kebab menus, the
 * Rank Detail "Invite" button, etc.) to the shared #roster-invite-modal.
 * Defaults the hidden "next" field to the current page so the invite POST
 * redirects back to wherever the trigger button lives.
 */
(function () {
  function initRosterInviteModal() {
    const rosterInviteModal = document.getElementById("roster-invite-modal");
    if (!rosterInviteModal) {
      return;
    }

    const rosterInviteForm = document.getElementById("roster-invite-form");
    const rosterInviteEmail = document.getElementById("roster-invite-email");
    const rosterInviteNext = document.getElementById("roster-invite-next");
    const rosterInvitePlayerName = document.getElementById(
      "roster-invite-player-name"
    );
    const modal = bootstrap.Modal.getOrCreateInstance(rosterInviteModal);

    document.querySelectorAll("[data-roster-invite]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        rosterInviteForm.action = button.dataset.inviteUrl;
        rosterInvitePlayerName.textContent = button.dataset.playerName;
        rosterInviteEmail.value = "";
        if (rosterInviteNext) {
          rosterInviteNext.value =
            window.location.pathname + window.location.search;
        }
        modal.show();
      });
    });

    rosterInviteModal.addEventListener("shown.bs.modal", () => {
      rosterInviteEmail.focus();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initRosterInviteModal);
  } else {
    initRosterInviteModal();
  }
})();
