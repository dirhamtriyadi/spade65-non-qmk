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

  // Browser code to the HID usage name compile_profile accepts. The macro
  // recorder writes these straight into a profile, so a name the compiler does
  // not know makes the whole profile unappliable.
  const USAGES = Object.freeze({
    Enter: "enter",
    Escape: "esc",
    Backspace: "backspace",
    Tab: "tab",
    Space: "space",
    Minus: "minus",
    Equal: "equal",
    BracketLeft: "left-bracket",
    BracketRight: "right-bracket",
    Backslash: "backslash",
    Semicolon: "semicolon",
    Quote: "quote",
    Backquote: "grave",
    Comma: "comma",
    Period: "dot",
    Slash: "slash",
    CapsLock: "caps-lock",
    PrintScreen: "print-screen",
    ScrollLock: "scroll-lock",
    Pause: "pause",
    Insert: "insert",
    Home: "home",
    PageUp: "page-up",
    Delete: "delete",
    End: "end",
    PageDown: "page-down",
    ArrowRight: "right",
    ArrowLeft: "left",
    ArrowDown: "down",
    ArrowUp: "up",
    ControlLeft: "left-ctrl",
    ShiftLeft: "left-shift",
    AltLeft: "left-alt",
    MetaLeft: "left-gui",
    ControlRight: "right-ctrl",
    ShiftRight: "right-shift",
    AltRight: "right-alt",
    MetaRight: "right-gui",
  });

  function usageForCode(code) {
    const name = String(code == null ? "" : code);
    if (!name) return null;
    if (/^Key[A-Z]$/.test(name)) return name.slice(3).toLowerCase();
    if (/^Digit[0-9]$/.test(name)) return name.slice(5);
    // The protocol defines f1 through f12 only. This keyboard advertises
    // KEY_F13..KEY_F24, and passing "f13" through produced a profile the
    // compiler rejected, so anything above f12 is left unmapped instead.
    const fkey = /^F([1-9]|1[0-2])$/.exec(name);
    if (fkey) return "f" + fkey[1];
    return Object.prototype.hasOwnProperty.call(USAGES, name) ?
      USAGES[name] :
      null;
  }

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
    USAGES,
    buttonsForCode,
    isHostReserved,
    isUnobservable,
    usageForCode,
  });
});
