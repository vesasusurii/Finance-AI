(function () {
  // React DOM checks `"oninput" in document` and, when false, probes support via
  // setAttribute("oninput", "return;"). That inline handler violates script-src
  // 'self' and shows as "Executing inline event handler" in the console.
  if (!("oninput" in document)) {
    Object.defineProperty(document, "oninput", {
      value: null,
      configurable: true,
      writable: true,
    });
  }

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
