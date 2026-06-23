(function () {
  document.querySelectorAll("[data-guest-login-prompt]").forEach((el) => {
    el.addEventListener("click", (event) => {
      event.preventDefault();
      window.alert(el.dataset.guestLoginPrompt);
    });
  });
})();
