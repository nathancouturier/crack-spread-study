# Vendored typefaces

Three variable fonts and their licences, pinned as bytes in this repository.
SPEC.md section 0.1: vendored libraries are pinned files in `/vendor` with their
licences, no CDN links. This folder holds fonts only. There is no chart library
here: `docs/design.md` Part 3 section 10 draws the charts as SVG by hand.

Nothing here needs a build step. The stylesheet loads each file with a path
relative to itself, `../vendor/...` from `styles/tokens.css`, and `index.html`
preloads two of them with `vendor/...`. The site is served from
`https://nathancouturier.github.io/crack-spread-study/`, a subpath, so a leading
slash in any of those URLs breaks the deploy. `tools/check-paths.mjs` fails the
gate on one.

## Where the bytes came from

Copied byte for byte on 2026-09-16 from the sibling repository
`lme-comex-arbitrage-model`, whose `vendor/README.md` records the original
fetch on 2026-09-02 from Google Fonts' own `latin` cuts, with the upstream URLs,
and the byte level verification (magic `wOF2`, declared length equal to size on
disk, a brotli stream that decompresses cleanly). Nothing was subset, converted
or renamed, here or there. The same bytes in both repositories means the two
sites draw the same letters.

## What is here, and the check that was run

| Path | Bytes | sha256 |
|---|---|---|
| `fraunces/fraunces.v1.000.latin.woff2` | 67,304 | `7234ed860a9cc83045413c4faee63c960a8f2d1917adcf728119307d56e0d783` |
| `fraunces/LICENSE` | 4,391 | `bdf4c22802eaf804f998195871c6b8938aac2ac14b2d78a8bd66a6f1eced833b` |
| `jetbrains-mono/jetbrains-mono.v2.211.latin.woff2` | 40,404 | `18be452724bfdc236c074ca94a249a7f41a86752c7d04ab258ce9ed5651f6a7e` |
| `jetbrains-mono/LICENSE` | 4,399 | `b2fe5e8987594e9ffd1d2ca52a2f5d73eb8335243893c5d6254b5ad69269591d` |
| `figtree/figtree.v2.002.latin.woff2` | 20,156 | `4ba7d3d096695818fe0686be4f1e82c6b05134e18a22260336130335027462dd` |
| `figtree/LICENSE` | 4,388 | `140d37233e7f3ce7313798befa9600893bcceaf41a55fa0fa5ad52f7f657a268` |

Every hash above was computed with `sha256sum vendor/*/*` on the copies in this
repository after copying, and every one equals the sibling's table. To check
again:

```
sha256sum vendor/*/*
```

127,864 bytes of font across three requests. Each file is variable, so weight is
an axis and not a separate file.

| Face | Version, name ID 5 | Licence | Upstream |
|---|---|---|---|
| Fraunces | 1.000 | SIL Open Font License 1.1, copyright 2018 The Fraunces Project Authors, no reserved font name | `https://github.com/undercasetype/Fraunces` |
| JetBrains Mono | 2.211 | SIL Open Font License 1.1, copyright 2020 The JetBrains Mono Project Authors, no reserved font name | `https://github.com/JetBrains/JetBrainsMono` |
| Figtree | 2.002 | SIL Open Font License 1.1, copyright 2022 The Figtree Project Authors, no reserved font name | `https://github.com/erikdkennedy/figtree` |

The OFL allows bundling and redistribution with software, provided the licence
travels with the font, which is why each `LICENSE` sits beside its file.

## Roles

| Face | Used for | Weights set in CSS |
|---|---|---|
| Fraunces | the verdict `h1`, view titles | 400 verdict, 500 view titles |
| Figtree | every word: nav, section names, summaries, headings, labels, captions, prose, figures inside a sentence | 400, 500, 600 |
| JetBrains Mono | figures in table cells and tick values on axes, nothing else | 400, 600 for totals |

`docs/design.md` Part 3 section 6 is the source of that table.

## The traps, read out of the files themselves

Measured on 2026-09-16 from the vendored bytes: the WOFF2 table directory was
parsed in node, the brotli stream decompressed with `node:zlib`, and `fvar`,
`GSUB` and `cmap` read directly. Nothing below comes from a vendor's
description.

```
fraunces        GSUB liga rvrn                                   opsz 9 default 9 max 144; wght 100 default 900 max 900
figtree         GSUB ccmp dnom frac locl numr pnum rvrn tnum     wght 300 default 300 max 900
jetbrains-mono  GSUB calt ccmp frac locl                         wght 100 default 400 max 800
```

1. **Fraunces defaults to Black at optical size 9.** The default instance of the
   `wght` axis is 900 and of `opsz` is 9. A rule that names Fraunces without a
   `font-weight` renders whatever the browser resolves `normal` against that
   axis, which is not the 400 the verdict wants. **Every rule that names
   Fraunces sets `font-weight`.** Leave `font-optical-sizing` at `auto` and
   never write `font-variation-settings`, which silently overrides
   `font-weight`. This is also why the portfolio's `h1, h2, h3, h4` rule,
   `font-variation-settings: "opsz" 144, "SOFT" 30`, is not copied. The shipped
   cut has no `SOFT` axis in any case.
2. **Fraunces lacks U+2191 and U+2193**, the up and down arrows, although
   Google's `unicode-range` for the cut declares them. A browser falls back to
   a system face for them mid sentence. Never set an arrow in Fraunces; the
   design bans arrows anyway. Fraunces does carry U+2212, the minus sign.
3. **Fraunces has no `tnum`.** Its GSUB lists `liga` and `rvrn` only, so
   `font-variant-numeric: tabular-nums` does nothing in it. The verdict's
   figures never update in place, so proportional digits there are harmless,
   and nothing that changes value live is set in Fraunces.
4. **Figtree's digits are not tabular by default.** It carries `tnum` and
   `pnum`, and proportional is the default. Every Figtree element that can hold
   a figure sets `font-variant-numeric: tabular-nums lining-nums`. There is no
   `onum`, so its figures are lining already and `lining-nums` states intent.
5. **Figtree defaults to Light 300.** The default instance of `wght` is 300 and
   name ID 1 reads `Figtree Light`. `styles/layout.css` sets `font-weight: 400`
   on `body` itself, and every Figtree rule that means 500 or 600 says so. A
   missed weight renders the page in Light, and 13px Light `--text-muted` is
   thinner than its measured 4.90 contrast suggests.
6. **JetBrains Mono needs nothing.** Its digits are one width by construction.
7. **None of the three carries U+263E or U+2600**, the moon and sun of the theme
   toggle, or U+FE0E. The toggle glyph falls back to a system face, and each
   glyph is followed by U+FE0E, the text presentation selector, so no platform
   draws it as a colour emoji. `docs/design.md` Part 3 section 6.

## Figtree stands in for Satoshi

The portfolio `nathancouturier.github.io` sets body text in Satoshi, and SPEC.md
section 0.2 names it. Satoshi is distributed under the ITF Free Font License,
whose section 02 forbids making the font software available through a
repository, a download service or a publicly accessible server. A public GitHub
repository is all three, so the file cannot be committed here. The portfolio
loads it from the Fontshare API, which is compliant for the portfolio, and
SPEC.md section 0.1 forbids CDN links in this project. The two rules cannot both
be kept with Satoshi.

Figtree is the openly licensed face the LME sibling measured as closest to
Satoshi at weight 400: x height 0.500 of the em against Satoshi's 0.484, cap
height 0.700 against 0.716, and a mean advance width difference of 4.95 percent
over `a-z`, `A-Z` and `0-9`, the smallest of five candidates on both measures
at once (Manrope, Onest, Plus Jakarta Sans and Inter were the others). The full
argument, the licence quotations and the measurement table are in
`lme-comex-arbitrage-model/vendor/README.md`, and are not repeated here.

The substitution is disclosed in three places and no others, `docs/design.md`
Part 3 section 6: this file, the known limitations in `README.md`, and one
sentence in the Method view. In CSS, `--ff-body` is redefined once, directly
after the verbatim token block in `styles/tokens.css`, with a comment naming the
substitution. If the owner ever obtains permission to redistribute Satoshi,
that line and one `@font-face` block are the only things that change.

## How the stylesheet loads them

| CSS family | URL from `styles/tokens.css` | `font-weight` range |
|---|---|---|
| `Fraunces` | `../vendor/fraunces/fraunces.v1.000.latin.woff2` | `100 900` |
| `JetBrains Mono` | `../vendor/jetbrains-mono/jetbrains-mono.v2.211.latin.woff2` | `100 800` |
| `Figtree` | `../vendor/figtree/figtree.v2.002.latin.woff2` | `300 900` |

`format("woff2")`, no `local()` first, because a visitor with another version
installed would otherwise see that one instead of the pinned bytes.
`font-display: swap`. `index.html` preloads Figtree then JetBrains Mono, each
with `crossorigin`, because fonts are fetched in anonymous mode even from the
same origin.

## Deliberately not here

- Satoshi, for the licence reason above.
- A chart library. `docs/design.md` Part 3 section 10.
- Italic, `latin-ext` or any other cut. The copy is English and never italic.
- Any CDN link. SPEC.md section 0.1.
