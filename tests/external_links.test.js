"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const externalLinks = require("../spade65/web/external-links.js");

const GUIDE_URL =
  "https://github.com/dirhamtriyadi/spade65-non-qmk/blob/main/docs/host-features.md";

function clickEvent() {
  let prevented = 0;
  return {
    event: {
      currentTarget: {href: GUIDE_URL},
      preventDefault() {
        prevented += 1;
      },
    },
    prevented: () => prevented,
  };
}

test("browser mode leaves the normal external anchor untouched", async () => {
  const click = clickEvent();
  const handler = externalLinks.createHandler(() => undefined);

  assert.equal(await handler(click.event), false);
  assert.equal(click.prevented(), 0);
});

test("the setup guide URL follows the supported UI language", () => {
  assert.equal(externalLinks.guideUrl("en"), GUIDE_URL);
  assert.equal(
    externalLinks.guideUrl("id"),
    "https://github.com/dirhamtriyadi/spade65-non-qmk/blob/main/docs/id/host-features.md",
  );
  assert.equal(externalLinks.guideUrl("future-language"), GUIDE_URL);
});

test("desktop mode prevents navigation and opens the exact link once", async () => {
  const click = clickEvent();
  const opened = [];
  const handler = externalLinks.createHandler(() => ({
    async open_external_url(url) {
      opened.push(url);
    },
  }));

  assert.equal(await handler(click.event), true);
  assert.equal(click.prevented(), 1);
  assert.deepEqual(opened, [GUIDE_URL]);
});

test("desktop opener failures stay in the app and reach the error callback", async () => {
  const click = clickEvent();
  const failure = new Error("browser unavailable");
  const errors = [];
  const handler = externalLinks.createHandler(
    () => ({
      async open_external_url() {
        throw failure;
      },
    }),
    error => errors.push(error),
  );

  assert.equal(await handler(click.event), false);
  assert.equal(click.prevented(), 1);
  assert.deepEqual(errors, [failure]);
});

test("binding attaches one handler to every external anchor", () => {
  const registrations = [];
  const links = Array.from({length: 4}, () => ({
    addEventListener(name, handler) {
      registrations.push([name, handler]);
    },
  }));
  const root = {
    querySelectorAll(selector) {
      assert.equal(selector, 'a[target="_blank"]');
      return links;
    },
  };
  const handler = () => {};

  assert.equal(externalLinks.bind(root, handler), 4);
  assert.deepEqual(registrations, links.map(() => ["click", handler]));
});
