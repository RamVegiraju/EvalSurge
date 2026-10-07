"use strict";

const fs = require("node:fs");
const vm = require("node:vm");

class Node {
  constructor(tag = "div") {
    this.tag = tag;
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this.value = "";
    this.checked = false;
    this.classes = new Set();
    this.classList = {
      add: value => this.classes.add(value),
      toggle: (value, enabled) => enabled ? this.classes.add(value) : this.classes.delete(value),
    };
  }

  set innerHTML(value) {
    throw new Error("HTML injection is forbidden");
  }

  set textContent(value) {
    this.text = String(value);
    this.children = [];
  }

  get textContent() {
    return (this.text ?? "") + this.children.map(child => child.textContent).join("");
  }

  append(...children) {
    this.children.push(...children);
  }

  replaceChildren(...children) {
    this.text = "";
    this.children = children;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  addEventListener(name, listener) {
    this.listeners[name] = listener;
  }

  querySelector(selector) {
    for (const child of this.children) {
      if (child.tag === selector) return child;
      const found = child.querySelector(selector);
      if (found) return found;
    }
    return null;
  }

  toJSON() {
    return {
      tag: this.tag, text: this.textContent, children: this.children,
      attributes: this.attributes, style: this.style, dataset: this.dataset,
      classes: [...this.classes], checked: this.checked,
      disabled: this.disabled, hidden: this.hidden,
    };
  }
}

async function main() {
  const input = JSON.parse(fs.readFileSync(0, "utf8"));
  const nodes = Object.fromEntries(input.ids.map(id => [id, new Node()]));
  const calls = [];
  const history = [];
  const context = vm.createContext({
    document: {
      createElement: tag => new Node(tag),
      getElementById: id => {
        if (!nodes[id]) throw new Error(`Missing element: ${id}`);
        return nodes[id];
      },
      querySelectorAll: selector => {
        if (selector !== "#heatmap tbody tr") throw new Error(`Unsupported selector: ${selector}`);
        return nodes.heatmap.children.find(child => child.tag === "tbody")?.children ?? [];
      },
    },
    URL, URLSearchParams,
    location: {
      search: input.autoload ? new URL(input.origin).search : "",
      href: input.origin ?? "http://localhost/reports/",
    },
    history: {replaceState: (...args) => history.push(args)},
    fetch: async (url, options) => {
      calls.push({url, options});
      const data = input.responses?.shift() ?? {ok: true, body: input.report};
      return {ok: data.ok, status: data.status ?? 200, json: async () => data.body};
    },
  });
  vm.runInContext(fs.readFileSync(input.script, "utf8"), context);
  if (input.autoload) {
    // The shipped initializer calls load(); let its bounded fixture promises settle.
    await new Promise(resolve => setImmediate(resolve));
  } else {
    nodes["run-id"].value = input.report.run.id;
    nodes["api-key"].value = "private-test-key";
    await vm.runInContext("load()", context);
  }
  if (input.toggle) {
    nodes["show-framework"].checked = true;
    await nodes["show-framework"].listeners.change();
  }
  if (input.select_missing) {
    const body = nodes.heatmap.children.find(child => child.tag === "tbody");
    await body.children.find(child => child.dataset.requestId === "missing").querySelector("button").listeners.click();
  }
  if (input.next) await nodes.next.listeners.click();
  if (input.invalid) {
    nodes["run-id"].value = "not-a-uuid";
    await nodes.connect.listeners.submit({preventDefault() {}});
  }
  process.stdout.write(JSON.stringify({nodes, calls, history}));
}

main().catch(error => {
  process.stderr.write(error.stack);
  process.exitCode = 1;
});
