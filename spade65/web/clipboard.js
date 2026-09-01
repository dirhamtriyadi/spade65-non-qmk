(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Spade65Clipboard = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const SERVICE_COMMAND_FIELDS = new Set([
    "prepare_commands",
    "activate_commands",
  ]);
  const MAX_CLIPBOARD_BYTES = 100000;

  function legacyCopy(text, documentNode) {
    if (
      !documentNode ||
      typeof documentNode.createElement !== "function" ||
      !documentNode.body ||
      typeof documentNode.body.append !== "function" ||
      typeof documentNode.execCommand !== "function"
    ) {
      throw new Error("legacy clipboard copy is unavailable");
    }

    const area = documentNode.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    area.setAttribute("readonly", "");

    try {
      documentNode.body.append(area);
      area.select();
      if (!documentNode.execCommand("copy")) {
        throw new Error("legacy clipboard copy failed");
      }
    } finally {
      if (typeof area.remove === "function") area.remove();
      else if (area.parentNode) area.parentNode.removeChild(area);
    }
  }

  function createCopier(nativeApi, browserClipboard, documentNode) {
    if (typeof nativeApi !== "function") {
      throw new TypeError("nativeApi must be a function");
    }
    if (typeof browserClipboard !== "function") {
      throw new TypeError("browserClipboard must be a function");
    }

    return async function copyServiceCommands(field, text) {
      if (!SERVICE_COMMAND_FIELDS.has(field)) {
        throw new TypeError("unknown service command field");
      }
      if (typeof text !== "string" || text.length === 0) {
        throw new TypeError("clipboard text must be a non-empty string");
      }
      if (text.includes("\0")) {
        throw new TypeError("clipboard text must not contain NUL characters");
      }
      if (new TextEncoder().encode(text).length > MAX_CLIPBOARD_BYTES) {
        throw new TypeError("clipboard text is too large");
      }

      const native = nativeApi();
      if (native && typeof native.copy_service_commands === "function") {
        await native.copy_service_commands(field);
        return "native";
      }

      try {
        const clipboard = browserClipboard();
        if (clipboard && typeof clipboard.writeText === "function") {
          await clipboard.writeText(text);
          return "browser";
        }
      } catch (_error) {
        // Embedded browsers can expose writeText while denying permission.
        // The user-activated legacy path is still worth trying.
      }

      legacyCopy(text, documentNode);
      return "legacy";
    };
  }

  return Object.freeze({
    createCopier
  });
});
