import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

function loadAppHooks() {
  const source = fs.readFileSync(new URL("../app/static/js/app.js", import.meta.url), "utf8");

  const emptyNode = {
    dataset: {},
    classList: {
      add() {},
      remove() {},
    },
    addEventListener() {},
    appendChild() {},
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
  };

  const context = {
    console,
    CSS: { escape(value) { return String(value); } },
    FormData: class {
      constructor() {}
      entries() {
        return [];
      }
    },
    fetch: async () => {
      throw new Error("fetch should not be called in this test");
    },
    document: {
      documentElement: { dataset: { appVersion: "test" } },
      getElementById() {
        return null;
      },
      querySelector() {
        return null;
      },
      querySelectorAll() {
        return [];
      },
      createElement() {
        return structuredClone(emptyNode);
      },
      body: {},
    },
    window: {
      location: { reload() {} },
      scrollTo() {},
      setTimeout() {},
      confirm() {
        return true;
      },
    },
  };

  context.globalThis = context;
  context.window.document = context.document;

  vm.runInNewContext(source, context, { filename: "app.js" });
  return context.window.__HCOPILOT_TEST_HOOKS__;
}

test("copilot stream error fallback keeps failure text instead of empty-result placeholder", () => {
  const hooks = loadAppHooks();

  assert.ok(hooks, "expected test hooks to be exposed from app.js");
  assert.equal(
    hooks.resolveCopilotFinalText({ finalAnswer: "", hasError: true }),
    "生成失败，请稍后重试。",
  );
});

function createClassList() {
  return {
    add() {},
    remove() {},
  };
}

function createReminderCard(list) {
  const card = {
    dataset: { reminderCard: "" },
    classList: createClassList(),
    removed: false,
    remove() {
      this.removed = true;
      list.children = list.children.filter((item) => item !== this);
    },
  };
  return card;
}

function createReminderList(children = []) {
  return {
    children: [...children],
    appendedNodes: [],
    querySelector(selector) {
      if (selector === "[data-reminder-empty-state]") {
        return this.children.find((item) => item.dataset?.reminderEmptyState !== undefined) || null;
      }
      return null;
    },
    querySelectorAll(selector) {
      if (selector === "[data-reminder-card]") {
        return this.children.filter((item) => item.dataset?.reminderCard !== undefined);
      }
      return [];
    },
    appendChild(node) {
      this.appendedNodes.push(node);
      this.children.push(node);
    },
  };
}

test("reminder delete success removes card and renders empty state when list becomes empty", () => {
  const hooks = loadAppHooks();
  const list = createReminderList();
  const card = createReminderCard(list);
  list.children.push(card);

  hooks.handleReminderDeleteSuccess({
    card,
    list,
    createEmptyState() {
      return { dataset: { reminderEmptyState: "" }, textContent: "还没有提醒，先创建一个吧。" };
    },
  });

  assert.equal(card.removed, true);
  assert.equal(list.querySelectorAll("[data-reminder-card]").length, 0);
  assert.equal(list.appendedNodes.length, 1);
  assert.equal(list.appendedNodes[0].textContent, "还没有提醒，先创建一个吧。");
});

test("reminder delete failure re-enables delete button and keeps card visible", () => {
  const hooks = loadAppHooks();
  const list = createReminderList();
  const card = createReminderCard(list);
  const button = { disabled: true };
  list.children.push(card);

  hooks.handleReminderDeleteFailure({ button });

  assert.equal(button.disabled, false);
  assert.equal(card.removed, false);
  assert.equal(list.querySelectorAll("[data-reminder-card]").length, 1);
});
