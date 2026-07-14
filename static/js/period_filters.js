(function () {
  function clearField(form, name) {
    const field = form.querySelector(`[name="${name}"]`);
    if (field) {
      field.value = "";
    }
  }

  function bindForm(form) {
    if (!form || form.dataset.periodFiltersBound === "1") {
      return;
    }
    form.dataset.periodFiltersBound = "1";

    const preset = form.querySelector('[data-period-control="preset"]');
    const year = form.querySelector('[data-period-control="year"]');
    const month = form.querySelector('[data-period-control="month"]');

    if (preset) {
      preset.addEventListener("change", function () {
        clearField(form, "year");
        clearField(form, "month");
        if (preset.value && preset.value !== "custom") {
          clearField(form, "start_date");
          clearField(form, "end_date");
          form.submit();
          return;
        }
        if (!preset.value) {
          clearField(form, "start_date");
          clearField(form, "end_date");
          form.submit();
          return;
        }
        // Custom: submit so the server shows From/To inputs.
        form.submit();
      });
    }

    if (year) {
      year.addEventListener("change", function () {
        clearField(form, "period_preset");
        clearField(form, "start_date");
        clearField(form, "end_date");
        form.submit();
      });
    }

    if (month) {
      month.addEventListener("change", function () {
        clearField(form, "period_preset");
        clearField(form, "start_date");
        clearField(form, "end_date");
        form.submit();
      });
    }
  }

  document
    .querySelectorAll(
      "form#leaderboard-filters, form#game-list-filters, form#ask-lodge-filters, form#group-standings-filters"
    )
    .forEach(bindForm);
})();
