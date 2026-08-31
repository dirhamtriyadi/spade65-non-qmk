(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Spade65UsagePicker = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  function normalizeSearch(value) {
    return String(value ?? "")
      .toLocaleLowerCase()
      .replace(/[-_/]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function usageHex(value) {
    return `0x${Number(value).toString(16).padStart(2, "0")}`;
  }

  function optionLabel(item) {
    return `${item.name} · ${item.hex}`;
  }

  function filterGroups(groups, usages, query, labelForGroup = String) {
    const tokens = normalizeSearch(query).split(" ").filter(Boolean);
    const results = [];
    for (const [group, names] of Object.entries(groups || {})) {
      const label = String(labelForGroup(group));
      const groupSearch = normalizeSearch(`${group} ${label}`);
      const wholeGroupMatches = tokens.length > 0 &&
        tokens.every(token => groupSearch.includes(token));
      const items = [];
      for (const name of names || []) {
        if (!Object.prototype.hasOwnProperty.call(usages || {}, name)) continue;
        const usage = Number(usages[name]);
        const hex = usageHex(usage);
        const itemSearch = normalizeSearch(
          `${name} ${group} ${label} ${hex} ${usage}`,
        );
        if (
          !tokens.length ||
          wholeGroupMatches ||
          tokens.every(token => itemSearch.includes(token))
        ) {
          items.push({
            name,
            usage,
            hex
          });
        }
      }
      if (items.length) results.push({
        group,
        label,
        items
      });
    }
    return results;
  }

  return Object.freeze({
    filterGroups,
    normalizeSearch,
    optionLabel,
    usageHex,
  });
});
