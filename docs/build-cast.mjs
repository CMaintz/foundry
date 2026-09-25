// Generates gate-demo.cast (asciinema v2) with correct ANSI escapes.
// Render: node docs/build-cast.mjs && npx svg-term-cli --in docs/gate-demo.cast --out docs/gate-demo.svg --window
import { writeFileSync } from 'node:fs';

const E = '\x1b';
const dim = (s) => `${E}[90m${s}${E}[0m`;
const cyan = (s) => `${E}[1;36m${s}${E}[0m`;
const ok = `${E}[1;32mok${E}[0m`;
const badge = `${E}[1;42m GATE GREEN ${E}[0m`;

const steps = [
  [0.4, dim('# one deterministic gate — while an agent edits, before you push, and on the PR') + '\r\n'],
  [0.9, cyan('$ mise run gate') + '\r\n'],
  [0.6, '  lint       ' + ok + '\r\n'],
  [0.5, '  typecheck  ' + ok + '\r\n'],
  [0.6, '  test       ' + ok + dim('  142 passed . coverage 91%') + '\r\n'],
  [0.6, '  audit      ' + ok + dim('  0 critical . secrets clean') + '\r\n'],
  [0.9, '  ' + badge + dim('  nothing merges without this') + '\r\n'],
  [1.3, '\r\n' + dim('# linters, types, tests & scanners hold sole authority — the LLM only proposes.') + '\r\n'],
  [1.4, ' '],
];

const header = { version: 2, width: 84, height: 13, env: { SHELL: '/bin/bash', TERM: 'xterm-256color' } };
let t = 0;
let out = JSON.stringify(header) + '\n';
for (const [d, text] of steps) {
  t += d;
  out += JSON.stringify([Number(t.toFixed(2)), 'o', text]) + '\n';
}
writeFileSync(new URL('./gate-demo.cast', import.meta.url), out);
console.log('wrote docs/gate-demo.cast');
