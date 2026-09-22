// Foundry prompt / agent-output regression harness — TypeScript (vitest).
//
// Generalises AutoApplicant's PromptEvalHarnessTest. Deterministic and OFFLINE: it scores
// hand-written good/weak samples with YOUR scorer and asserts the scorer RANKS them —
// good >= FLOOR, weak <= CEILING, and the gap >= SEPARATION. Separation is the trustworthy
// signal (a scorer earns trust by ranking; an absolute cutoff on hand-written text is
// arbitrary). It also checks the composed prompt still carries the blocks a fixture needs,
// so a prompt regression is caught here, not in a bad output weeks later.
//
// This runs under `test` — it IS a test, no new verb. foundry ships NO scorer: you provide
// `scoreOutput` (your deterministic quality scorer) and optionally `composePrompt`.
//
// RATCHET: the fixture COUNT may only grow — never delete a regression case. Enforced on
// manifest.json by ruleset-guard's `coverage` kind. Do NOT ratchet the SCORES upward:
// chasing an ever-higher floor overfits the scorer, which is exactly the game-the-proxy
// failure agent-loop.md warns against. The thresholds below are ruleset (guard-watched via
// the ruleset-file watch — lowering FLOOR / raising CEILING / lowering SEPARATION needs a
// human label), not a ratchet.

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
// You implement these in your repo — they are the domain-specific half foundry does not ship:
//   scoreOutput(output, input) -> number   (your deterministic quality score, 0..100)
//   composePrompt(input) -> string         (optional; only if you assert prompt blocks)
import { composePrompt, scoreOutput } from "./your-scorer";

const FLOOR = 80; // a good sample must clear this
const CEILING = 60; // a weak sample must stay under this
const SEPARATION = 30; // the gap that makes the score trustworthy as a regression metric

interface Fixture {
  name: string;
  input: string;
  good: string;
  weak: string;
  expectedBlocks?: string[]; // substrings the composed prompt must contain
}

const here = (p: string) => new URL(p, import.meta.url);
const manifest: { fixtures: string[] } = JSON.parse(readFileSync(here("./manifest.json"), "utf8"));
const fixtures: Fixture[] = manifest.fixtures.map(
  (f) => JSON.parse(readFileSync(here(`./fixtures/${f}`), "utf8")),
);

describe("prompt eval", () => {
  it.each(fixtures)("$name — scorer separates good from weak", (f) => {
    const good = scoreOutput(f.good, f.input);
    const weak = scoreOutput(f.weak, f.input);
    expect(good, `good sample for ${f.name}`).toBeGreaterThanOrEqual(FLOOR);
    expect(weak, `weak sample for ${f.name}`).toBeLessThanOrEqual(CEILING);
    expect(good - weak, `separation for ${f.name}`).toBeGreaterThanOrEqual(SEPARATION);
  });

  const withBlocks = fixtures.filter((f) => f.expectedBlocks?.length);
  it.each(withBlocks)("$name — composed prompt carries required blocks", (f) => {
    const prompt = composePrompt(f.input);
    for (const block of f.expectedBlocks ?? []) {
      expect(prompt, `prompt for ${f.name} missing block: ${block}`).toContain(block);
    }
  });
});
