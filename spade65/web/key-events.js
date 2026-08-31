(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Spade65KeyEvents = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  // Browser KeyboardEvent.code values are layout-independent physical
  // positions, which is exactly what the tester needs: it reports where the
  // firmware thinks a key sits, after any remap the profile applied.
  const DIRECT = Object.freeze({
    Escape: "esc",
    Minus: "minus",
    Equal: "plus",
    Backspace: "bksp",
    Tab: "tab",
    BracketLeft: "lqu",
    BracketRight: "rqu",
    Delete: "delete",
    CapsLock: "caps",
    Semicolon: "sem",
    Quote: "quo",
    Enter: "enter",
    PageUp: "pageup",
    ShiftLeft: "lshift",
    ShiftRight: "rshift",
    Comma: "comma",
    Period: "dot",
    Slash: "qmark",
    ArrowUp: "up",
    PageDown: "pagedown",
    ControlLeft: "lctrl",
    MetaLeft: "win",
    AltLeft: "lalt",
    AltRight: "ralt",
    ControlRight: "rctrl",
    ArrowLeft: "left",
    ArrowDown: "down",
    ArrowRight: "right",
  });

  // The board resolves Fn internally and never emits a usage for it, so no
  // tester on any host can observe it. Reported so the page can say why.
  const UNOBSERVABLE = Object.freeze(["fn"]);

  // The desktop or window manager commonly claims these before the page sees
  // them, so a key that stays dark here is not proof the key is broken.
  const HOST_RESERVED = Object.freeze(["win"]);

  const SPACE_BUTTONS = Object.freeze(["lspace", "mspace", "rspace"]);

  function isIso(variant) {
    return String(variant || "").startsWith("iso");
  }

  function buttonsForCode(code, variant) {
    const name = String(code || "");
    if (!name) return [];
    if (name === "Space") return SPACE_BUTTONS.slice();
    if (Object.prototype.hasOwnProperty.call(DIRECT, name)) return [DIRECT[name]];
    if (/^Key[A-Z]$/.test(name)) return [name.slice(3).toLowerCase()];
    if (/^Digit[0-9]$/.test(name)) return ["n" + name.slice(5)];
    // The vendor matrix keeps both a k29 and a k42 slot. ANSI puts the
    // backslash above a one-row Enter (k29); ISO moves it beside a tall Enter
    // (k42). The browser reports "Backslash" for both physical positions.
    if (name === "Backslash") return [isIso(variant) ? "k42" : "k29"];
    return [];
  }

  function isUnobservable(button) {
    return UNOBSERVABLE.includes(button);
  }

  function isHostReserved(button) {
    return HOST_RESERVED.includes(button);
  }

  return Object.freeze({
    DIRECT,
    HOST_RESERVED,
    SPACE_BUTTONS,
    UNOBSERVABLE,
    buttonsForCode,
    isHostReserved,
    isUnobservable,
  });
});
