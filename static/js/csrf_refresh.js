(function () {
  var refreshTimer = null;

  function getCsrfTokenFromCookie() {
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function updateCsrfInputs(token, root) {
    if (!token) {
      return;
    }
    var scope = root && root.querySelector ? root : document;
    scope
      .querySelectorAll('input[name="csrfmiddlewaretoken"]')
      .forEach(function (input) {
        input.value = token;
      });
  }

  function syncCsrfFromCookie(root) {
    updateCsrfInputs(getCsrfTokenFromCookie(), root);
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
      syncCsrfFromCookie();
      scheduleCsrfRefresh();
    }
  });

  window.addEventListener("pageshow", function (event) {
    syncCsrfFromCookie();
    if (event.persisted) {
      scheduleCsrfRefresh();
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    syncCsrfFromCookie();
    scheduleCsrfRefresh();
  });

  document.addEventListener(
    "submit",
    function (event) {
      var form = event.target;
      if (!form || !form.querySelector) {
        return;
      }
      if (!form.querySelector('input[name="csrfmiddlewaretoken"]')) {
        return;
      }
      syncCsrfFromCookie(form);
    },
    true,
  );
})();
