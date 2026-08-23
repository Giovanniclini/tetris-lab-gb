# CLAUDE.md — Project principles for AI coding sessions

Read this before doing anything substantial in this repository.

---

## What this project is

**Tetris Lab GB (`tetris-lab-gb`) is a training/practice ROM for the original Nintendo Game Boy
version of Tetris (1989), modelled on TetrisGYM for the NES.**

Renamed from `tetris-gym-gb` in August 2026 at TetrisGYM's author's request. **Do not reintroduce
"gym" into the name, the ROM title, or user-facing text.** References to TetrisGYM itself are
correct and should stay.

It is modelled on [TetrisGYM](https://github.com/kirjavascript/TetrisGYM) for NES Tetris: a practice
mod built **on top of a disassembly of the original game**, distributed as a patch, that adds
training functionality while leaving the original gameplay intact.

It is **not** a new Tetris implementation, and **not** a modernisation.

---

## Read these before making implementation decisions

| Document | Contains |
| --- | --- |
| `docs/research.md` | Technical research: TetrisGYM analysis, Game Boy Tetris internals, disassembly evaluation and **local build verification**, hardware constraints, the ROM-hack-vs-rewrite decision, legal/distribution notes |
| `docs/community-research.md` | Community research, evidence strength, the full feature matrix, and the **TOP 10 features** |
| `docs/architecture.md` | Current architecture decisions (D1–D8), repository layout, the original/Lab code boundary, memory plan, build system, testing strategy |
| `docs/roadmap.md` | Current milestones and acceptance criteria |
| `docs/existing-hacks.md` | Reverse engineering of the community's ROM hacks — KLM's extended gravity table, the SPS LFSR, what we must match |
| `docs/decisions/` | Architecture Decision Records — **read these before touching Lab code**; they record constraints found the hard way (bank switching, hook style, level-select gotchas) |

**If a task touches architecture, memory layout, the build, the ROM version, or the
original/Lab boundary, read the relevant document first.** These documents contain measured facts
(free-space figures, verified hashes, exact frame timings) that are expensive to re-derive and easy
to get wrong from memory.

---

## Core principles

### 1. Preserving original Game Boy Tetris behaviour is a core goal

Authenticity *is* the product. A trainer whose physics differ from the real game trains the wrong
reflexes and is worse than useless. The original gameplay must remain **bit-for-bit the original
machine code**.

Concretely, these must never drift: gravity (the per-level table at `$1B06`), DAS (23 frames
initial / 9 autorepeat), ARE (2 frames), line-clear delay (93 frames), the biased OR-rejection
randomizer, left-handed Nintendo Rotation System, 10×18 playfield, the scoring formula, and the
original's line-clear quirk (only 16 of 18 rows are checked).

**The 999 999 score cap is not on that list**, and used to be. *Corrected 2026-08-21 after
Tolstoj pushed back.* Everything above changes how the game *plays*, so a trainer that alters one
teaches the wrong reflexes. A score ceiling teaches nothing — it only limits what you can record,
and the community already competes on KLM's uncapped score
(`docs/community-research.md` §3.5.1). Keeping it as the default is right; treating it as
untouchable was wrong.

Note what the cap actually is before extending it: `wScoreBCD` is **three BCD bytes**, so 999 999
is the ceiling of the storage, not a policy. The clamp at `$0178` writes `$99 $99 $99` on carry-out
to stop it wrapping to zero. An uncap therefore means widening the score — storage, the in-game
display, and `HISCORE_Score1`, which is also three bytes — not deleting five bytes of clamp.

### 2. Do not replace the original game with a new Tetris implementation

The project has explicitly decided (`docs/architecture.md` D1) to modify a disassembly rather than
write an engine. **Do not write a Tetris engine, a board model, a piece model, a rotation system or
a randomizer.** They already exist, in the ROM, correct.

If you ever believe a rewrite is warranted, **stop and ask the user.** Do not begin one.

### 3. The original/Lab boundary is sacred

* `src/original/` is **vendored, not forked**. Every deviation from upstream is enumerated in
  `src/original/UPSTREAM.md`.
* All new functionality lives in `src/lab/` (ROM banks 2+).
* The **only** permitted edits to original banks 0–1 are **declared hooks** in `src/hooks/hooks.inc`.
* **Prefer changing state over changing code.** Most trainers need no hook at all: set up WRAM and
  the tilemap before gameplay starts, then let the untouched original code run. A hook is the
  last resort, not the first tool.
* Adding a hook is a significant change. Declare it, justify it, update the expected hook table in
  `tests/test_original.py`, and flag it clearly to the user.

### 4. The byte-exactness test is the project's ground truth

```
python3 build.py --original   →   SHA-1 74591cc9501af93873f9a5d3eb12da12c0723bbc
```

This must pass on every commit. **If it fails, the change is wrong** — regardless of how good the
new feature looks. Never "temporarily" disable, skip, or weaken this test. If you cannot make a
change while keeping it green, that is information about the change, not about the test.

The second-order test — banks 0–1 differ from the reference only at declared hook addresses — has
the same status.

### 5. Do not silently change major architectural decisions

The decisions in `docs/architecture.md` (§1, D1–D8) and the target ROM version (`Tetris (World)
Rev A`, v1.1) were made from measured evidence. Changing any of them requires:

1. saying so explicitly to the user, with the reasoning;
2. an ADR in `docs/decisions/`;
3. an update to `docs/architecture.md`.

Never change one as a side effect of another task.

### 6. Keep the documentation current as you go

Docs are part of the change, not a follow-up. Before finishing any piece of work, update whatever it
made untrue:

| If you… | Update |
| --- | --- |
| finish or start a milestone | `docs/roadmap.md` — the **only** place status lives |
| add or change a hook in the original banks | `src/hooks/hooks.inc`, `src/original/UPSTREAM.md`, `tests/test_expansion.py` |
| add a player-visible feature | `README.md` feature list |
| make a decision that constrains future work | a new ADR in `docs/decisions/` |
| learn something measured about the ROM or the community | `docs/research.md`, `docs/community-research.md` or `docs/existing-hacks.md` |

Stale documentation is worse than none: it gets trusted. If you find something out of date, fix it
in the same change rather than noting it.

ADRs should be short — context, decision, consequences, and any trap found the hard way.

### 7. Write briefly

Prefer fewer words. Concretely:

* State the finding, not the search for it. Working notes belong in the commit message, not the docs.
* One example beats three.
* Tables beat paragraphs for anything enumerable.
* Do not restate in prose what a code comment or a test already says — link to it.
* Comments explain *why*; the code already says what.

This applies to commit messages, PR descriptions and replies as much as to files.

### 7a. One concept, one commit

A branch that does one thing lands as **one commit**. Fixing your own work in
progress is not a second concept: four attempts at where a digit goes is still
"uncap the score". Squash before pushing, or `git reset --soft main` and recommit
if the branch already has a history.

Split commits only when a branch genuinely carries **unrelated** concepts — a
score uncap and a rocket-scene skip in the same PR is two commits, because
either could be reverted without the other. Prefer separate PRs when that
happens at all.

What each commit message should carry is in §7: what changed, why, and what it
cost to find. A squashed message is longer than any of the ones it replaces, and
should be — it is the only record that survives.

**Force-pushing a feature branch to squash it is fine.** Force-pushing `main` is
not (§8).

### 8. Do not make destructive changes

No force-pushes, no history rewrites, no deleting or wholesale-rewriting `src/original/`, no
removing tests to make a build pass. Do not commit or push unless the user asks. If on `main`,
branch first.

### 9. Do not install system-wide dependencies without asking

`python3 build.py` must keep working on a clean machine with **only Python 3 and network access** —
no `make`, no `gcc`, no package manager, no global installs. RGBDS is downloaded to
`build/toolchain/`, verified by SHA-256, and used from there.

If you believe a system-wide dependency is genuinely required, **ask first** and explain why the
vendored approach cannot work.

### 10a. Credit the community's work, and ask before taking more

Two things in this ROM are not ours: the **LFSR** is Toni's 24-bit design, and the **L/M gravity
values** match KLM by reverse engineering. Both are
deliberate — interoperability is the point — and both must stay credited in `README.md` §Credits
and in the source that uses them.

**ROMs shared privately are shared privately.** Do not redistribute them, do not commit them, and
do not lift code from them without asking the person who sent them. *"It's more than likely ok, but
I am a person that needs this"* — Tolstoj, 2026-08-21. Ask first; name people after.

### 10. Never distribute ROM data

The Game Boy Tetris ROM is copyrighted. Releases contain a **BPS patch only**. Never commit a
`.gb`/`.gbc` file, never attach one to a release or an issue, never paste ROM bytes into a
conversation. Users supply their own ROM. `.gb` is in `.gitignore` — keep it there.

### 11. Respect the platform's real constraints

Measured, not guessed (`docs/research.md` §4):

* The original 32 KB ROM has **~400 usable free bytes**. Everything new goes in banks 2+.
* **HRAM has 2 free bytes.** WRAM has ~4.5 KB free. Use WRAM.
* **VBlank (~1.09 ms) is the scarcest resource**, and the original handler is already near-full.
  All Lab rendering goes through one hook and a dirty-flag queue with a per-frame tile budget.
  Never do arithmetic in VBlank. Prefer sprites for small indicators.
* Rendering that cannot fit the budget gets redesigned or dropped. It does not get to steal time
  from the original render path, because that would change original timing.

### 12. Scope discipline

Out of scope by decision, not omission: hold, hard drop, ghost piece, SRS, multi-piece preview,
PAL/NTSC modes, Game Boy Color enhancement, Super Game Boy support.
[Tetris — Rosy Retrospection](https://www.romhacking.net/hacks/5813/) already serves the
"modernised Game Boy Tetris" audience well; this project deliberately does not compete with it.

If asked to add one of these, say it conflicts with a recorded decision, point at
`docs/community-research.md` §5 (rows 21–27), and let the user decide.

---

## Practical notes

* **Assembly is RGBDS syntax for the Sharp SM83.** Pinned version: **RGBDS v0.6.1**. RGBDS 1.0
  removed pre-1.0 `EQU` syntax and breaks every Game Boy Tetris disassembly — do not upgrade
  casually; treat it as its own task gated on byte-exactness.
* **Build outputs `.map` and `.sym`.** The map drives free-space accounting; the sym file drives
  symbolic debugging in BGB/Emulicious and the test harness. Both are mandatory.
* **The playfield is the VRAM background tilemap**, with a WRAM shadow at `wTileMap` (`$C800`).
  The active piece is four OAM sprites. There is no board array. Empty cells are the space tile.
* **SPS ("same piece sequence") is the community's #1 ask and has been for five years** — see
  `docs/community-research.md` §3.5.3. It is also nearly free on Game Boy: the original already
  reads pieces from a 256-byte `wRandomness` table at `$C300` for demos and 2-player mode. Seeded,
  drought and scripted sequences all reduce to filling that table and forcing that branch.
  **Do not write a new generator.**
* **We are not first, and must not ship a downgrade.** The community already uses a de-facto
  standard "KLM" romhack (level starts **A–M** = 10–22 with an extended gravity/scoring table, plus
  score uncap) and a separate 40-line sprint ROM with a built-in timer. Matching those is table
  stakes. **Our differentiator is the foundation** — buildable from source, byte-exact against the
  original, regression-tested — not the feature list. `docs/community-research.md` §3.5.1.
* **Instant restart already exists** — `A+B+Select+Start` is a soft reset in the original.
* **Input recording is half-built** — `RecordDemo` runs every frame but is inert unless `$FFE9`
  is `$FF`.
* When you need a number (a timing, an address, a free-space figure), **check `docs/research.md`
  first** — it was measured locally, and its addresses are v1.1-specific. Several published sources
  describe v1.0 or v1.1 without saying which; the gravity table is at `$1B06` in v1.1 but `$1B61`
  in v1.0.

---

## Current status

**See `docs/roadmap.md`.** It is the single source of truth; do not restate status here or in the
README, or it goes stale in three places at once.
