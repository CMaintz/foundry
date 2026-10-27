#!/usr/bin/env node
// prettier-config - write a .prettierrc.json that matches a repo's existing JS/TS style,
// unless the repo already configures Prettier.
//
//   Usage: node prettier-config.mjs [dir] [--print]
//     dir      the package to configure (default ".")
//     --print  print the inferred config and write nothing, even when a config exists
//
// Without a config, Prettier formats to its own defaults, and the first `mise run fix`
// restyles every file that differs. Inferring the options that drive churn (semicolons,
// quotes, indentation, trailing commas, line width) from the code already there keeps that
// first run close to a no-op. A repo with no code yet gets Prettier's defaults.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const CONFIG_FILES = [
  '.prettierrc',
  ...['json', 'json5', 'yaml', 'yml', 'toml', 'js', 'cjs', 'mjs', 'ts', 'cts', 'mts'].map((e) => `.prettierrc.${e}`),
  ...['js', 'cjs', 'mjs', 'ts', 'cts', 'mts'].map((e) => `prettier.config.${e}`),
];
const SOURCE = /\.(ts|tsx|mts|cts|js|jsx|mjs|cjs)$/;
const SKIP_DIRS = /(^|\/)(node_modules|dist|build|coverage|vendor)\//;
const MAX_FILES = 400;
// Prettier adds trailing commas to .jsonc too, and hand-written JSONC (wrangler, knip)
// conventionally has none, so it would otherwise be the one thing the first run restyles.
const JSONC_OVERRIDE = { overrides: [{ files: '*.jsonc', options: { trailingComma: 'none' } }] };

function configuredHere(dir) {
  if (CONFIG_FILES.some((f) => existsSync(join(dir, f)))) return true;
  const pkg = join(dir, 'package.json');
  if (!existsSync(pkg)) return false;
  try {
    return JSON.parse(readFileSync(pkg, 'utf8')).prettier !== undefined;
  } catch {
    return false;
  }
}

function gitRoot(dir) {
  try {
    return resolve(execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd: dir, encoding: 'utf8' }).trim());
  } catch {
    return resolve(dir);
  }
}

// Prettier resolves its config upward from each file, so a config anywhere between the
// package and the repo root already governs the package; a new one would override it.
export function hasPrettierConfig(dir) {
  const root = gitRoot(dir);
  for (let d = resolve(dir); ; d = dirname(d)) {
    if (configuredHere(d)) return true;
    if (d === root || d === dirname(d)) return false;
  }
}

// -z keeps git from quoting non-ASCII names; tracked files deleted from the worktree are
// still listed, so only files that exist are read.
function listSources(dir) {
  let files;
  try {
    files = execFileSync('git', ['ls-files', '-zco', '--exclude-standard'], { cwd: dir, encoding: 'utf8' }).split('\0');
  } catch {
    return [];
  }
  const sources = files.filter((f) => SOURCE.test(f) && !SKIP_DIRS.test(f) && existsSync(join(dir, f)));
  return sources.slice(0, MAX_FILES);
}

// Comment and blank lines say nothing about code style, and would skew every ratio below.
export function codeLines(text) {
  return text
    .split(/\r?\n/)
    .filter((l) => l.trim() !== '' && !/^\s*(\/\/|\/\*|\*)/.test(l));
}

// A semicolon-style file still has lines ending in `)` or a name (multi-line expressions),
// so `semi: false` is chosen only when semicolon endings are clearly the minority.
export function inferSemi(lines) {
  const semi = lines.filter((l) => /;\s*$/.test(l)).length;
  const bare = lines.filter((l) => /[\w)\]'"`]\s*$/.test(l)).length;
  return semi + bare === 0 || semi / (semi + bare) >= 0.3;
}

export function inferSingleQuote(lines) {
  const text = lines.join('\n');
  const single = (text.match(/'(?:[^'\\\n]|\\.)*'/g) || []).length;
  const double = (text.match(/"(?:[^"\\\n]|\\.)*"/g) || []).length;
  return single > double;
}

// The indent step is the most common increase between consecutive space-indented lines.
export function inferIndent(lines) {
  const tabs = lines.filter((l) => l.startsWith('\t')).length;
  const spaced = lines.filter((l) => l.startsWith(' ')).length;
  if (tabs > spaced) return { useTabs: true };
  const steps = { 2: 0, 4: 0 };
  let prev = 0;
  for (const l of lines) {
    const indent = l.length - l.trimStart().length;
    if (indent - prev in steps) steps[indent - prev]++;
    prev = indent;
  }
  return { useTabs: false, tabWidth: steps[4] > steps[2] ? 4 : 2 };
}

// The line before a closer is a list's last element only sometimes: before a `}` it is
// usually a block's last statement, which never takes a comma either way. So a `}` counts
// only after a `key: value` line, and never after a `;` (TS interface and type members).
function lastElementBefore(closer, prev) {
  if (/[([{;]$/.test(prev)) return false;
  return closer !== '}' || prev.endsWith(',') || /^\s*[\w$'"[\]]+\??\s*:/.test(prev);
}

// es5 means trailing commas in multi-line arrays and objects but never in call or parameter
// lists. Most comma-less `)` lines are conditions or JSX groups, which take no comma under
// any setting, so es5 shows as call-list commas being nearly absent rather than outvoted.
export function inferTrailingComma(lines) {
  const count = { bracket: [0, 0], paren: [0, 0] };
  for (let i = 1; i < lines.length; i++) {
    const closer = lines[i].trim()[0];
    const prev = lines[i - 1].trimEnd();
    if (!')]}'.includes(closer) || !lastElementBefore(closer, prev)) continue;
    count[closer === ')' ? 'paren' : 'bracket'][prev.endsWith(',') ? 0 : 1]++;
  }
  if (count.bracket[0] <= count.bracket[1]) return 'none';
  const callCommaRare = count.paren[1] > 0 && count.paren[0] < 0.05 * count.bracket[0];
  return callCommaRare ? 'es5' : 'all';
}

// Prettier only lets a line run past printWidth when it cannot break it, so code formatted
// at a width has almost no lines over it. The narrowest width with under 1% of lines over
// it is the one in use; picking too narrow a width rewraps, too wide a width joins lines.
export function inferPrintWidth(lines) {
  for (const width of [80, 100, 120]) {
    const over = lines.filter((l) => l.length > width).length;
    if (over / Math.max(lines.length, 1) < 0.01) return width;
  }
  return 120;
}

export function inferConfig(dir) {
  const lines = listSources(dir).flatMap((f) => codeLines(readFileSync(join(dir, f), 'utf8')));
  if (lines.length === 0) return {};
  const trailingComma = inferTrailingComma(lines);
  return {
    printWidth: inferPrintWidth(lines),
    semi: inferSemi(lines),
    singleQuote: inferSingleQuote(lines),
    ...inferIndent(lines),
    trailingComma,
    ...(trailingComma !== 'none' && JSONC_OVERRIDE),
  };
}

function main(argv) {
  const print = argv.includes('--print');
  const dir = argv.find((a) => !a.startsWith('--')) ?? '.';
  if (!print && hasPrettierConfig(dir)) {
    console.log(`  skip (Prettier already configured): ${dir}`);
    return;
  }
  const config = inferConfig(dir);
  const json = `${JSON.stringify(config, null, 2)}\n`;
  if (print) {
    process.stdout.write(json);
    return;
  }
  writeFileSync(join(dir, '.prettierrc.json'), json);
  const how = Object.keys(config).length ? 'inferred from the existing code' : "Prettier's defaults (no JS/TS yet)";
  console.log(`  wrote: ${join(dir, '.prettierrc.json')} (${how}): ${JSON.stringify(config)}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  main(process.argv.slice(2));
}
