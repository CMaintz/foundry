# LinkedIn launch assets

- `post.md` — the post copy (long + short variant) and posting notes.
- `deck.html` — the 12-slide carousel source. Portrait 1080×1350 (4:5), one
  `<section class="slide">` per page, fonts vendored under `fonts/` so it renders
  identically offline.
- `foundry-linkedin-deck.pdf` — the rendered carousel. This is the file LinkedIn
  takes as a document post.

## Rebuild

```sh
chromium --headless --no-pdf-header-footer --virtual-time-budget=6000 \
  --print-to-pdf=foundry-linkedin-deck.pdf "file://$PWD/deck.html"
```

Page size comes from `@page { size: 1080px 1350px; margin: 0 }`. Each slide is a
fixed-height flex column — if you add copy, re-check that nothing overflows:

```sh
chromium --headless --dump-dom --virtual-time-budget=4000 "file://$PWD/deck.html" \
  | grep -o "<title>[^<]*</title>"
```

Every slide must report `1350`. Anything higher is clipped in the PDF.
