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

  function rawUsageValue(value) {
    const normalized = String(value ?? "").trim();
    if (!/^(?:0x[\da-f]+|0|[1-9]\d*)$/i.test(normalized)) return null;
    const usage = Number(normalized);
    return Number.isInteger(usage) && usage >= 0 && usage <= 0xff ? usage : null;
  }

  function resolveUsage(usages, value) {
    const normalized = String(value ?? "").trim().toLocaleLowerCase();
    if (!normalized) return null;
    if (Object.prototype.hasOwnProperty.call(usages || {}, normalized)) {
      const usage = Number(usages[normalized]);
      return {
        name: normalized,
        usage,
        hex: usageHex(usage),
      };
    }
    const raw = rawUsageValue(normalized);
    if (raw === null) return null;
    for (const [name, value] of Object.entries(usages || {})) {
      if (Number(value) === raw) {
        return {
          name,
          usage: raw,
          hex: usageHex(raw),
        };
      }
    }
    return null;
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
    rawUsageValue,
    resolveUsage,
    usageHex,
  });
});
