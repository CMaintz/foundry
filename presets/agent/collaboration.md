# Collaboration — how agents share a repo

Copy the relevant lines into your repo's `AGENTS.md` / `CLAUDE.md`, or `@`-include
this file. Language-agnostic. This is about *working discipline*, not code style
(that's `code-standards.md`).

## Branch hygiene (parallel sessions)

Multiple agent sessions run against the same working copy at once. Whatever branch
happens to be checked out is **not yours** — another session may have put it there
mid-task. So, before doing any work:

```sh
git fetch origin
git switch -c <type>/<short-desc> origin/main   # feat/… fix/… chore/… docs/…
```

- **Start from `origin/main`, on your own fresh branch.** Never commit onto whatever
  branch is currently checked out — you'll interleave your commits with another
  session's and poison both PRs.
- **One branch → one PR → one concern.** If the work splits into two concerns, cut
  a second branch off `origin/main`; don't pile them onto one branch.
- **Don't retarget or stack onto a branch you didn't create.** If you must build on
  unmerged work, confirm it's actually merged first (a squash-merge leaves the
  source branch's commits orphaned — the branch looks "ahead", but its work is in).
- **Rebase, don't merge main in.** When your branch falls behind, `git rebase
  origin/main` — keep history linear and the PR diff honest.

## Delegate to sub-agents — don't do everything in one thread

Default to spinning up sub-agents for work that is independent, read-heavy, or
parallelisable. Most agents under-use this and grind through it serially.

- **Explore / read-many** → an exploration sub-agent returns the *conclusion*, not
  twenty file dumps in your context. Use it whenever answering means sweeping many
  files or you're hunting for where something lives.
- **Independent slices** → fan out one agent per slice/file when they don't touch
  the same code; run them in a single batch so they go concurrently (give each its
  own git worktree if they'll edit in parallel).
- **Verify / adversarial** → a fresh agent prompted to *refute* a finding catches
  what the authoring thread has already rationalised away.

Keep the main thread as the orchestrator that decides and integrates; push the
legwork out. Rule of thumb: if you're about to read your fifth file to answer one
question, that's a sub-agent.

## Why it's a Foundry standard

Colliding sessions is the single most expensive failure mode of multi-agent work:
two sessions on one branch produce a PR that neither can cleanly own, and untangling
it costs more than the work itself. A one-line `git switch -c … origin/main` at the
start makes the collision structurally impossible.
