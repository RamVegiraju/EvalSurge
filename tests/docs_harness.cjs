"use strict";

const fs = require("node:fs");
const vm = require("node:vm");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
let settings;
const bundle = configuration => { settings = configuration; };
bundle.presets = {apis: {}};
vm.runInNewContext(fs.readFileSync(input.script, "utf8"), {
  window: {location: {href: input.origin}},
  URL,
  SwaggerUIBundle: bundle,
}, {codeGeneration: {strings: false, wasm: false}});
process.stdout.write(JSON.stringify(settings));
