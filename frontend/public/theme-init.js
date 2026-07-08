(function () {
  var storageKey = "theme";
  var theme = localStorage.getItem(storageKey);
  var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  if (
    theme === "dark" ||
    (!theme && prefersDark) ||
    (theme === "system" && prefersDark)
  ) {
    document.documentElement.classList.add("dark");
  }
})();
