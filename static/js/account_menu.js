(function () {
  var resetBtn = document.getElementById("reset-preferences-btn");
  if (!resetBtn) {
    return;
  }

  resetBtn.addEventListener("click", function () {
    if (
      !window.confirm(
        "Reset all saved preferences? This cannot be undone.",
      )
    ) {
      return;
    }

    var url = resetBtn.dataset.url;
    var csrf =
      (window.leaderlodgeGetCsrfToken && window.leaderlodgeGetCsrfToken()) ||
      (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ||
      "";

    fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": csrf },
      credentials: "same-origin",
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.ok) {
          window.location.reload();
        }
      })
      .catch(function () {
        window.alert("Could not reset preferences. Please try again.");
      });
  });
})();
