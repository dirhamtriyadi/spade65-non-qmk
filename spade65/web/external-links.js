(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Spade65ExternalLinks = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const REPOSITORY_URL = "https://github.com/dirhamtriyadi/spade65-non-qmk";

  function guideUrl(language) {
    const languagePath = language === "id" ? "id/" : "";
    return `${REPOSITORY_URL}/blob/main/docs/${languagePath}host-features.md`;
  }

  function createHandler(nativeApi, onError = () => {}) {
    if (typeof nativeApi !== "function") {
      throw new TypeError("nativeApi must be a function");
    }
    if (typeof onError !== "function") {
      throw new TypeError("onError must be a function");
    }
    return async function openExternalLink(event) {
      const native = nativeApi();
      if (!native || typeof native.open_external_url !== "function") return false;
      event.preventDefault();
      try {
        await native.open_external_url(event.currentTarget.href);
        return true;
      } catch (error) {
        onError(error);
        return false;
      }
    };
  }

  function bind(rootNode, handler) {
    if (!rootNode || typeof rootNode.querySelectorAll !== "function") {
      throw new TypeError("rootNode must support querySelectorAll");
    }
    if (typeof handler !== "function") {
      throw new TypeError("handler must be a function");
    }
    const links = Array.from(rootNode.querySelectorAll('a[target="_blank"]'));
    for (const link of links) link.addEventListener("click", handler);
    return links.length;
  }

  return Object.freeze({
    bind,
    createHandler,
    guideUrl,
  });
});
