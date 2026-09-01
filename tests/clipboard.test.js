"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const clipboard = require("../spade65/web/clipboard.js");

const PREPARATION_COMMANDS = [
  "mkdir -p ~/.config/spade65",
  "./Spade65.AppImage service example > ~/.config/spade65/service.json",
].join("\n");
const ACTIVATION_COMMANDS = [
  "mkdir -p ~/.config/systemd/user",
  "systemctl --user enable --now spade65.service",
].join("\n");

function legacyDocument({execResult = true, execError = null} = {}) {
  const calls = {
    appended: [],
    commands: [],
    created: [],
    removed: 0,
    selected: 0,
  };
  const documentNode = {
    body: {
      append(node) {
        calls.appended.push(node);
        node.parentNode = this;
      },
      removeChild(node) {
        node.parentNode = null;
        calls.removed += 1;
      },
    },
    createElement(tagName) {
      const attributes = {};
      const area = {
        attributes,
        parentNode: null,
        style: {},
        value: "",
        remove() {
          this.parentNode = null;
          calls.removed += 1;
        },
        select() {
          calls.selected += 1;
        },
        setAttribute(name, value) {
          attributes[name] = value;
        },
      };
      calls.created.push([tagName, area]);
      return area;
    },
    execCommand(command) {
      calls.commands.push(command);
      if (execError) throw execError;
      return execResult;
    },
  };
  return {calls, documentNode};
}

test("preparation copy uses the late-bound canonical native command", async () => {
  const nativeWrites = [];
  const browserWrites = [];
  let native;
  let nativeLookups = 0;
  const copyText = clipboard.createCopier(
    () => {
      nativeLookups += 1;
      return native;
    },
    () => ({writeText: text => browserWrites.push(text)}),
    legacyDocument().documentNode,
  );
  native = {
    async copy_service_commands(field) {
      nativeWrites.push(field);
    },
  };

  assert.equal(
    await copyText("prepare_commands", PREPARATION_COMMANDS),
    "native",
  );
  assert.equal(nativeLookups, 1);
  assert.deepEqual(nativeWrites, ["prepare_commands"]);
  assert.deepEqual(browserWrites, []);
});

test("activation copy selects the canonical native activation command", async () => {
  const nativeWrites = [];
  const copyText = clipboard.createCopier(
    () => ({
      async copy_service_commands(field) {
        nativeWrites.push(field);
      },
    }),
    () => {
      throw new Error("browser clipboard must not be inspected");
    },
    legacyDocument().documentNode,
  );

  assert.equal(
    await copyText("activate_commands", ACTIVATION_COMMANDS),
    "native",
  );
  assert.deepEqual(nativeWrites, ["activate_commands"]);
});

test("browser mode uses Clipboard API when no native bridge exists", async () => {
  const writes = [];
  const legacy = legacyDocument();
  const copyText = clipboard.createCopier(
    () => undefined,
    () => ({
      async writeText(text) {
        writes.push(text);
      },
    }),
    legacy.documentNode,
  );

  assert.equal(
    await copyText("prepare_commands", PREPARATION_COMMANDS),
    "browser",
  );
  assert.deepEqual(writes, [PREPARATION_COMMANDS]);
  assert.deepEqual(legacy.calls.created, []);
});

test("native rejection is reported without bypassing the native boundary", async () => {
  const attempts = [];
  const copyText = clipboard.createCopier(
    () => ({
      async copy_service_commands(field) {
        attempts.push(["native", field]);
        throw new Error("native clipboard unavailable");
      },
    }),
    () => ({
      async writeText(text) {
        attempts.push(["browser", text]);
      },
    }),
    legacyDocument().documentNode,
  );

  await assert.rejects(
    copyText("activate_commands", ACTIVATION_COMMANDS),
    /native clipboard unavailable/,
  );
  assert.deepEqual(attempts, [["native", "activate_commands"]]);
});

test("browser rejection falls back to a selected temporary textarea", async () => {
  const legacy = legacyDocument();
  const copyText = clipboard.createCopier(
    () => undefined,
    () => ({
      async writeText() {
        throw new Error("clipboard permission denied");
      },
    }),
    legacy.documentNode,
  );

  assert.equal(
    await copyText("prepare_commands", PREPARATION_COMMANDS),
    "legacy",
  );
  assert.equal(legacy.calls.created.length, 1);
  const [tagName, area] = legacy.calls.created[0];
  assert.equal(tagName, "textarea");
  assert.equal(area.value, PREPARATION_COMMANDS);
  assert.equal(area.style.position, "fixed");
  assert.equal(area.style.opacity, "0");
  assert.equal(area.attributes.readonly, "");
  assert.equal(legacy.calls.selected, 1);
  assert.deepEqual(legacy.calls.commands, ["copy"]);
  assert.equal(legacy.calls.removed, 1);
  assert.equal(area.parentNode, null);
});

test("missing Clipboard API uses the legacy copy path", async () => {
  const legacy = legacyDocument();
  const copyText = clipboard.createCopier(
    () => undefined,
    () => undefined,
    legacy.documentNode,
  );

  assert.equal(
    await copyText("activate_commands", ACTIVATION_COMMANDS),
    "legacy",
  );
  assert.equal(legacy.calls.removed, 1);
});

test("legacy false result rejects and still removes the textarea", async () => {
  const legacy = legacyDocument({execResult: false});
  const copyText = clipboard.createCopier(
    () => undefined,
    () => undefined,
    legacy.documentNode,
  );

  await assert.rejects(
    copyText("prepare_commands", PREPARATION_COMMANDS),
    /legacy clipboard copy failed/,
  );
  assert.equal(legacy.calls.removed, 1);
  assert.equal(legacy.calls.created[0][1].parentNode, null);
});

test("legacy execCommand exceptions reject and still remove the textarea", async () => {
  const failure = new Error("clipboard backend crashed");
  const legacy = legacyDocument({execError: failure});
  const copyText = clipboard.createCopier(
    () => undefined,
    () => undefined,
    legacy.documentNode,
  );

  await assert.rejects(
    copyText("activate_commands", ACTIVATION_COMMANDS),
    failure,
  );
  assert.equal(legacy.calls.removed, 1);
  assert.equal(legacy.calls.created[0][1].parentNode, null);
});

test("invalid text is rejected before any clipboard lookup", async () => {
  let nativeLookups = 0;
  let browserLookups = 0;
  const copyText = clipboard.createCopier(
    () => {
      nativeLookups += 1;
    },
    () => {
      browserLookups += 1;
    },
    legacyDocument().documentNode,
  );

  for (const value of [undefined, null, 17, {}, ""]) {
    await assert.rejects(
      copyText("prepare_commands", value),
      /clipboard text must be a non-empty string/,
    );
  }
  assert.equal(nativeLookups, 0);
  assert.equal(browserLookups, 0);
});

test("unknown fields and NUL text are rejected before clipboard lookup", async () => {
  let lookups = 0;
  const copyText = clipboard.createCopier(
    () => {
      lookups += 1;
    },
    () => {
      lookups += 1;
    },
    legacyDocument().documentNode,
  );

  await assert.rejects(
    copyText("firmware_commands", PREPARATION_COMMANDS),
    /unknown service command field/,
  );
  await assert.rejects(
    copyText("prepare_commands", "safe\0unsafe"),
    /must not contain NUL/,
  );
  await assert.rejects(
    copyText("prepare_commands", "é".repeat(50001)),
    /too large/,
  );
  assert.equal(lookups, 0);
});

test("createCopier rejects non-callable late-bound getters", () => {
  assert.throws(
    () => clipboard.createCopier(null, () => undefined, undefined),
    /nativeApi must be a function/,
  );
  assert.throws(
    () => clipboard.createCopier(() => undefined, null, undefined),
    /browserClipboard must be a function/,
  );
});
