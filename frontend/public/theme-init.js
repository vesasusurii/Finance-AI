(function () {
  // React DOM checks `"oninput" in document` and, when false, probes support via
  // setAttribute("oninput", "return;"). That inline handler violates script-src
  // 'self' and shows as "Executing inline event handler" in the console.
  try {
    Object.defineProperty(document, "oninput", {
      value: null,
      configurable: true,
      writable: true,
    });
  } catch (_e) {
    // Already defined in some browsers; setAttribute guard below still applies.
  }

  function isInlineEventHandlerAttribute(name, value) {
    return (
      typeof name === "string" &&
      name.length > 2 &&
      name.charCodeAt(0) === 111 &&
      name.charCodeAt(1) === 110 &&
      typeof value === "string"
    );
  }

  var nativeSetAttribute = Element.prototype.setAttribute;
  Element.prototype.setAttribute = function (name, value) {
    if (isInlineEventHandlerAttribute(name, value)) {
      return;
    }
    return nativeSetAttribute.call(this, name, value);
  };

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
