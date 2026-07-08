/**
 * Neutralise React DOM's inline on* feature-detection probes under strict CSP.
 * Imported first from main.tsx; index.html also inlines the same logic with a
 * CSP hash so it runs before any external script can load.
 */
(function applyCspPolyfill() {
  try {
    Object.defineProperty(document, "oninput", {
      value: null,
      configurable: true,
      writable: true,
    });
  } catch {
    // Some browsers already expose oninput on document.
  }

  function isInlineEventHandlerAttribute(name: unknown, value: unknown): boolean {
    return (
      typeof name === "string" &&
      name.length > 2 &&
      name.charCodeAt(0) === 111 &&
      name.charCodeAt(1) === 110 &&
      typeof value === "string"
    );
  }

  const nativeSetAttribute = Element.prototype.setAttribute;
  Element.prototype.setAttribute = function (
    name: string,
    value: string,
  ): void {
    if (isInlineEventHandlerAttribute(name, value)) {
      return;
    }
    nativeSetAttribute.call(this, name, value);
  };

  const nativeSetAttributeNS = Element.prototype.setAttributeNS;
  if (nativeSetAttributeNS) {
    Element.prototype.setAttributeNS = function (
      namespace: string | null,
      name: string,
      value: string,
    ): void {
      if (isInlineEventHandlerAttribute(name, value)) {
        return;
      }
      nativeSetAttributeNS.call(this, namespace, name, value);
    };
  }
})();
