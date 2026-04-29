#!/usr/bin/env node

import fs from "node:fs";
import process from "node:process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const acorn = require("./vendor/node_modules/acorn");
const walk = require("./vendor/node_modules/acorn-walk");
const tsPluginModule = require("./vendor/node_modules/acorn-typescript");

const tsPlugin =
  typeof tsPluginModule === "function"
    ? tsPluginModule
    : tsPluginModule.default || tsPluginModule.tsPlugin;

const VISIBLE_KEYS = new Set([
  "title",
  "subtitle",
  "heading",
  "caption",
  "body",
  "text",
  "content",
  "label",
  "footer",
]);

const CALL_NAMES = new Set([
  "addText",
  "text",
  "addTitle",
  "addSubtitle",
  "addCaption",
  "addNotes",
]);

function parserFor(surface) {
  if (surface === "ts") {
    return acorn.Parser.extend(tsPlugin());
  }
  return acorn.Parser;
}

function safeString(node) {
  if (!node) return null;
  if (node.type === "Literal" && typeof node.value === "string") {
    return node.value;
  }
  if (node.type === "TemplateLiteral" && node.expressions.length === 0) {
    return node.quasis.map((q) => q.value.cooked || "").join("");
  }
  return null;
}

function propertyName(node) {
  if (!node) return null;
  if (node.type === "Identifier") return node.name;
  if (node.type === "Literal" && typeof node.value === "string") return node.value;
  return null;
}

function emit(units, node, text, context) {
  if (!text) return;
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) return;
  units.push({
    line_no: node?.loc?.start?.line || 1,
    text: cleaned,
    context,
  });
}

function extractFromRuns(node, units, contextPrefix) {
  if (!node) return;
  if (node.type !== "ArrayExpression") return;
  for (const item of node.elements || []) {
    if (!item || item.type !== "ObjectExpression") continue;
    for (const prop of item.properties || []) {
      if (prop.type !== "Property") continue;
      const name = propertyName(prop.key);
      if (name !== "text") continue;
      emit(units, prop.value, safeString(prop.value), `${contextPrefix}:text`);
    }
  }
}

function extractCallText(callNode, units, calleeName) {
  const [firstArg] = callNode.arguments || [];
  if (!firstArg) return;
  emit(units, firstArg, safeString(firstArg), `call:${calleeName}`);
  extractFromRuns(firstArg, units, `call:${calleeName}`);
}

function main() {
  const file = process.argv[2];
  const surface = process.argv[3] || "js";
  if (!file) {
    console.error("usage: extract_visible_strings.mjs <file> <surface>");
    process.exit(2);
  }

  const source = fs.readFileSync(file, "utf8");
  const Parser = parserFor(surface);

  let ast;
  try {
    ast = Parser.parse(source, {
      ecmaVersion: "latest",
      sourceType: "module",
      locations: true,
      allowHashBang: true,
    });
  } catch (error) {
    console.error(String(error));
    process.exit(1);
  }

  const units = [];

  walk.simple(ast, {
    Property(node) {
      const keyName = propertyName(node.key);
      if (!VISIBLE_KEYS.has(keyName)) return;
      emit(units, node.value, safeString(node.value), `property:${keyName}`);
      extractFromRuns(node.value, units, `property:${keyName}`);
    },
    CallExpression(node) {
      let calleeName = null;
      if (node.callee?.type === "Identifier") {
        calleeName = node.callee.name;
      } else if (node.callee?.type === "MemberExpression") {
        calleeName = propertyName(node.callee.property);
      }
      if (!calleeName || !CALL_NAMES.has(calleeName)) return;
      extractCallText(node, units, calleeName);
    },
  });

  process.stdout.write(JSON.stringify({ units }, null, 2));
}

main();
