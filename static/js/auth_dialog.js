(function () {
  var dialogEl = document.getElementById("guest-auth-dialog");
  if (!dialogEl) {
    return;
  }

  var messageEl = dialogEl.querySelector("[data-guest-auth-dialog-message]");
  var defaultEl = dialogEl.querySelector("[data-guest-auth-dialog-default]");
  var modal = bootstrap.Modal.getOrCreateInstance(dialogEl);

  function closeParentDropdown(el) {
    var dropdownMenu = el.closest(".dropdown-menu");
    if (!dropdownMenu || !dropdownMenu.parentElement) {
      return;
    }
    var toggle = dropdownMenu.parentElement.querySelector(
      '[data-bs-toggle="dropdown"]',
    );
    if (!toggle) {
      return;
    }
    var dropdown = bootstrap.Dropdown.getInstance(toggle);
    if (dropdown) {
      dropdown.hide();
    }
  }

  function showGuestAuthDialog(message) {
    var text = (message || "").trim();
    if (messageEl && defaultEl) {
      if (text) {
        messageEl.textContent = text;
        messageEl.classList.remove("d-none");
        defaultEl.classList.add("d-none");
      } else {
        messageEl.textContent = "";
        messageEl.classList.add("d-none");
        defaultEl.classList.remove("d-none");
      }
    }
    modal.show();
  }

  window.leaderlodgeShowGuestAuthDialog = showGuestAuthDialog;

  document
    .querySelectorAll("[data-guest-auth-trigger], [data-guest-login-prompt]")
    .forEach(function (el) {
      el.addEventListener("click", function (event) {
        event.preventDefault();
        closeParentDropdown(el);
        var msg =
          el.dataset.guestAuthMessage || el.dataset.guestLoginPrompt || "";
        showGuestAuthDialog(msg);
      });
    });
})();
