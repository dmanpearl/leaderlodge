(function () {
  var refreshTimer = null;

  function getCsrfTokenFromCookie() {
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function updateCsrfInputs(token) {
    if (!token) {
      return;
    }
    document
      .querySelectorAll('input[name="csrfmiddlewaretoken"]')
      .forEach(function (input) {
        input.value = token;
      });
  }

  function refreshCsrfTokens() {
    var url = document.body.dataset.csrfRefreshUrl;
    if (!url) {
      return;
    }

    fetch(url, { credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) {
          return null;
        }
        return response.json();
      })
      .then(function (data) {
        if (data && data.csrfToken) {
          updateCsrfInputs(data.csrfToken);
        }
      })
      .catch(function () {
        /* ignore; form may still work if token is fresh */
      });
  }

  function scheduleCsrfRefresh() {
    if (refreshTimer) {
      window.clearTimeout(refreshTimer);
    }
    refreshTimer = window.setTimeout(refreshCsrfTokens, 100);
  }

  window.leaderlodgeGetCsrfToken = getCsrfTokenFromCookie;

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") {
      scheduleCsrfRefresh();
    }
  });

  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      scheduleCsrfRefresh();
    }
  });
})();
