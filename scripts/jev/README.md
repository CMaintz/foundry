# scripts/jev - Foundry's advisory Jev layer

Near-free [Jev](https://typesafe.ai) (TypeSafe System One) decisions for the
**proposer** side of Foundry: which diff hunks deserve deep review and on which
lens, and whether a turn looks destructive. This is where Jev earns its place -
upstream of the expensive LLM, never upstream of the deterministic oracle.

## The one rule

Jev is ~68% accurate, so it **never** sits in the authoritative gate
(`lint` / `typecheck` / `test` / `audit`). It only routes and triages: a wrong
call costs a missed shortcut, never a false pass. `boundary.test.mjs` fails the
build if any CI workflow or mise gate verb ever references this directory.

## Pieces

- `client.mjs` - the `JevProvider` port (`TypeSafeProvider`, `CloudflareProvider`,
  `postJson` with 429/529 backoff) plus `providerFromEnv`, which returns `null`
  when no key is set so every caller fails open to current behavior.
- `route.mjs` - pure, no-network core: `routeReview(answers, cfg)`,
  `triageToolcall(answer, cfg)`, and the question templates. Fail-open is the
  invariant: a missing or low-confidence answer always widens review, never narrows it.

## Usage

```js
import { providerFromEnv } from './scripts/jev/client.mjs';
import { reviewQuestions, routeReview } from './scripts/jev/route.mjs';

const jev = providerFromEnv();
if (!jev) return; // no key: skip Jev, review everything as before

const { answers } = await jev.evaluate({
  state: { file, hunk, ticket },
  questions: reviewQuestions(),
});
const { review, lens, reason } = routeReview(answers);
// review only the above-threshold hunks, on `lens`; log the rest (still get baseline review).
```

Or run the ready-made review pre-filter over a diff and consume its routing JSON:

```
node scripts/jev/review.mjs [baseRef]          # baseRef defaults to origin/main
JEV_REVIEW_MIN_FILES=8 node scripts/jev/review.mjs   # skip Jev on small diffs
```

It prints, per changed file, `{ review, lens, reason }`. No key (or a diff at/under the
min-files gate) routes every file to review - Jev only ever narrows spend, never the net.

## Config

Read from the environment (keys never in CI):
`JEV_API_KEY`, `JEV_PROVIDER` (`typesafe` | `cloudflare`), `JEV_MODEL`
(defaults to `jev-latest`), `CLOUDFLARE_ACCOUNT_ID`, and `TYPESAFE_AI_BASE_URL`
(point the direct call at a self-host, proxy, or mock). `review.mjs` also reads
`JEV_REVIEW_MIN_FILES`.

The non-secret knobs have a commented, opt-in home in each mise template's
`[env]` block (the "Jev (advisory layer)" group), so a repo centralizes them in
one place instead of scattering exports. Note the reach: a mise `[env]` value
only lands in processes started via `mise run` / `mise exec` or a mise-activated
shell, so a Claude Code hook picks it up only when the editor was launched from
such a shell. The key is never committed; export `JEV_API_KEY` in the shell.

## Tests

```
node --test scripts/jev/*.test.mjs
```
