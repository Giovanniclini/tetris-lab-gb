# Architecture

**Status:** Proposed, 2026-08-20. No code written yet.
**Decision basis:** `docs/research.md` (technical) and `docs/community-research.md` (product).

---

## 1. Decisions

| # | Decision | Rationale |
| --- | --- | --- |
| **D1** | **Modify a disassembly of the original game. Do not write a new Tetris engine.** | Authenticity *is* the product. A trainer whose physics differ from the game trains the wrong reflexes. The disassembly route gets perfect fidelity for free and lets us prove it with a checksum. `docs/research.md` §5. |
| **D2** | **Target `Tetris (World) (Rev A)` — "v1.1".** MD5 `982ed5d2b12a0377eb14bcdc4123744e`, SHA-1 `74591cc9501af93873f9a5d3eb12da12c0723bbc`. | The version bundled with ~30 M Game Boys, the version the reference docs describe, the one with the sane level curve. v1.0 is a ~10 000-unit Japanese prototype with an easier level progression. |
| **D3** | **Foundation: [`vinheim3/tetris-gb-disasm`](https://github.com/vinheim3/tetris-gb-disasm), vendored into `src/original/`.** | MIT-licensed, 100 % coverage, heavily commented, per-subsystem files — and **it built byte-exact here on the first attempt with zero patches**. `docs/research.md` §2.2. |
| **D4** | **Pin RGBDS v0.6.1**, vendored by URL + SHA-256, not installed system-wide. | The repo targets it and it is verified working. RGBDS 1.0 removed pre-1.0 `EQU` syntax and breaks every GB Tetris disassembly. Toolchain drift is the most likely cause of upstream issue #6. |
| **D5** | **Expand the cartridge to MBC1, 64 KB ROM (4 banks), 8 KB battery SRAM** (cart type `$03`). **PROVISIONAL — see D9.** | The original 32 KB ROM has **~400 usable free bytes**. This is arithmetic, not preference. The original already writes `1` to `$2000`, so MBC1 conversion is nearly free. Note this is *not* a copy of TetrisGYM: retail NES Tetris is already MMC1 and TetrisGYM's default build fits inside its original 32 KB. We have far less slack. `docs/research.md` §4.1–4.2. |
| **D6** | **Banks 0 and 1 remain byte-identical to the original except for a small, enumerated hook table.** Every Lab byte lives in bank 2+. | Makes "did we change the original game?" a mechanical question answerable by `cmp`, and keeps the release BPS patch small and auditable. |
| **D7** | **Distribute a BPS patch only. Never publish a `.gb`.** | The ROM is copyrighted. `docs/research.md` §7. |
| **D8** | **Lab code is authored in RGBDS assembly; build orchestration and asset tooling in Python 3 (stdlib only).** | Python 3 is already present on typical dev machines and in CI; `make`/`gcc` are not universally available. Keeps `git clone && python3 build.py` working with no system-wide installs. |
| **D9** | **SRAM is optional at build time (`--no-sram`), and the mapper choice is not final until the cart-production board is known.** | The GBTetris Discord intends to produce physical carts once SPS + extended level select exist (`docs/community-research.md` §3.4). That makes the cartridge a **design input we can influence**, not a constraint imposed on users. Batteries add BOM cost and die; savestates and persisted config must degrade to session-only without SRAM, and the ROM must boot without it. MBC5 may be cheaper than MBC1 on modern repro boards — **confirm with Gunter before locking D5** (§7 A10). |

---

## 2. Repository layout

```
tetris-lab-gb/
├── CLAUDE.md                  project principles; read this first
├── CONTRIBUTING.md            branch-and-PR workflow, what CI checks
├── build.py                   the entire build; no make, no gcc
├── requirements-dev.txt       test-only dependency (PyBoy)
├── docs/
│   ├── research.md            technical research
│   ├── community-research.md  community evidence, feature matrix, top 10
│   ├── existing-hacks.md      reverse engineering of the community's ROMs
│   ├── architecture.md        this file
│   ├── roadmap.md             milestones and status  <-- single source of truth
│   └── decisions/             ADRs, one per constraining decision
├── src/
│   ├── original/              VENDORED, see UPSTREAM.md  <-- section 3
│   ├── hooks/                 the only edits to original banks
│   │   ├── hooks.inc          the declared hook table
│   │   └── trampoline.inc     FarCall and the state-dispatch stub
│   └── lab/
│       ├── lab.asm            the include list, and nothing else
│       ├── state.asm          every byte the Lab owns, HRAM and WRAM
│       ├── dispatch.asm       opens the bank 2 section; one branch per hooked state
│       ├── level_select.asm   the 0-9 grid plus the A-M level field
│       ├── seed.asm           the six seed digits, and arming the LFSR
│       ├── high_scores.asm    filing and drawing, seventh digit included
│       ├── menu.asm           the title screen, replaced
│       ├── drills.asm         trainers: TRANSITION so far
│       ├── gameplay.asm       corrections to how the game plays
│       ├── scoring.asm        the score's seventh digit on screen
│       ├── rendering.asm      the two tilemap primitives
│       ├── restart.asm        A+B+Select+Start restarts the drill
│       ├── random.asm         the SPS LFSR (lives in bank 1's empty space)
│       ├── gravity.inc        extended 23-entry gravity table
│       ├── levels.inc         shared level constants
│       └── softreset.inc      bank-0 stub for instant restart
├── tools/
│   ├── rgbds.py               fetch and verify the pinned toolchain
│   ├── gfx.py                 PNG -> 2bpp/1bpp with asserted sizes
│   ├── patch.py               apply UPS/BPS patches
│   ├── analyze_hack.py        diff a community ROM against our build
│   └── emu.py                 headless emulator harness
├── tests/
│   ├── test_original.py       byte-exactness and original constants
│   ├── test_expansion.py      the declared-hooks diff
│   ├── test_behaviour.py      gravity, hearts, timings
│   ├── test_menu.py           level picker
│   ├── test_restart.py        instant restart
│   └── test_sps.py            seeded piece sequences
└── build/                     gitignored: toolchain/, obj/, *.gb, *.sym, *.map
```

`src/lab/` is flat while it is small. Split it into subdirectories when a
directory would hold more than a handful of files, not before.


---

## 3. The boundary between original code and Lab code

This is the most important structural rule in the project.

### 3.1 `src/original/` is vendored, not forked

It is a verbatim copy of the upstream disassembly at a pinned commit. **Every deviation from
upstream must be listed in `src/original/UPSTREAM.md`** with a one-line justification. There are
exactly three categories of permitted deviation:

1. **Toolchain migration** — syntax changes required by the pinned RGBDS version. Must not change a
   single output byte.
2. **Section splitting** — e.g. splitting the monolithic `include/wram.s` into named per-purpose
   sections so the linker can report real free space (`docs/research.md` §3.4). Must not change a
   single output byte.
3. **Hook insertion points** — see §3.2. These *do* change bytes, and each one is enumerated.

Categories 1 and 2 are verified by the byte-exactness test. Category 3 is verified by the
hook-budget test.

### 3.2 Hooks: the only writes into original banks

A **hook** replaces a small number of bytes in bank 0 or 1 with a call into Lab code. Every hook:

* is declared in `src/hooks/hooks.inc` with its address, byte length, and purpose;
* is guarded by `IF DEF(LAB)` so a `LAB=0` build reproduces the original ROM exactly;
* is counted by `tests/test_original.py`, which asserts the total number of changed bytes in banks
  0–1 matches the declared hook table **exactly** — no undeclared drift.

```asm
; src/hooks/hooks.inc  (illustrative)
;
;   name              addr    len  purpose
;   HOOK_SPAWN_PIECE  $2xxx    3   redirect piece selection to the Lab sequencer
;   HOOK_VBLANK_END   $0xxx    3   render the Lab HUD after the original VBlank work
;   HOOK_STATE_TABLE  $0xxx    2   point an unused hGameState slot at the Lab menu
;   HOOK_SOFT_RESET   $0xxx    3   restart the current trainer instead of rebooting
```

Hooks are **`call`s into a bank-0 trampoline**, never direct far-jumps, because the caller may be in
any bank. Keep the trampoline in reclaimed bank-0 filler (`$005B–$00FF`, 165 bytes — the unused
space between the serial interrupt vector and the `$0100` entry point).

**Design rule: prefer changing *state* over changing *code*.** Most trainers in the feature matrix
need no hook at all — they set up WRAM/tilemap before gameplay starts and then let the untouched
original code run. Reach for a hook only when per-frame behaviour must change. Hooks are the
project's scarcest and most dangerous resource; every one is a place original behaviour can drift.

### 3.3 Bank map

| Bank | Contents | Editable? |
| --- | --- | --- |
| 0 (`$0000–$3FFF`) | Original code + header + **Lab trampoline** in reclaimed filler | Hooks only |
| 1 (`$4000–$7FFF`) | Original bank 1 (demo data, sound engine) | Hooks only |
| 2 | Lab core: menu, state machine, sequencer, HUD | Free |
| 3 | Lab trainers (`modes/`) | Free |
| 4 | Lab data: preset boards, tilemaps, strings | Free |
| 5–7 | Reserved for growth | Free |

Banked calls use a standard trampoline that saves the current bank, switches, calls, and restores:

```asm
; ROM0, in reclaimed filler
FarCall::           ; in: b = target bank, hl = target address
    ld   a, [hCurrentBank]
    push af
    ld   a, b
    ld   [hCurrentBank], a
    ld   [$2000], a          ; MBC1 ROM bank select
    call .jump_hl
    pop  af
    ld   [hCurrentBank], a
    ld   [$2000], a
    ret
.jump_hl:
    jp   hl
```

`hCurrentBank` must live in **HRAM**, but HRAM has only 2 free bytes (`$FFFD–$FFFE`).
`$FFFD` is the natural home. This is one of the few genuinely tight resources — see §6.

---

## 4. Memory

### 4.1 WRAM

> **CORRECTED 2026-08-20.** An earlier draft of this section listed ~4.5 KB of free WRAM, including
> `$C400–$C7FF`, taken from `meithecatte/gbtetris`'s memory map. That map simply declares no section
> there. `vinheim3` — which we build from, and which has 100 % coverage — shows **`$C400–$C7FF` is
> used** by `wDarkSolidBlocksUnderRandomBlocks`. Do not trust the old figures.

The one large, **verified** free region is **`$D762–$DF6F` — 2 062 bytes** between the high-score
tables and the audio variables. No code anywhere in the disassembly references an address in that
range (checked by scanning every `$Dxxx` literal in `src/original/`).

Not *quite* free: the original's own high-score indexing runs past the end of its ten-slot table for
any level above the grid, straight into `$D762`. Those 351 bytes are claimed as the continuation of
that table rather than defended against — see `docs/decisions/0006`.

| Range | Size | Assigned to |
| --- | --- | --- |
| `$D762–$D8C0` | 351 B | **A-type high scores, levels A–M** — 13 slots continuing `wATypeHighScores` |
| `$D8C1–$DCC0` | 1 024 B | **Lab core state** — active trainer, config, timer, statistics, HUD dirty flags |
| `$DCC1–$DF6F` | 687 B | free |

Smaller unlabelled gaps exist lower in WRAM (`$C0DF–$C1FF`, and upstream notes that
`wDemoOrMultiplayerPieces` at `$C300` is *"actually $30 in size"* despite reserving `$100`). **Treat
them as used until proven otherwise** — the `$C400` mistake above is exactly how that goes wrong.

Upstream declares WRAM as one monolithic section, so the linker reports no free space at all. The
split that exposes the gap is deviation #2 in `src/original/UPSTREAM.md`; it moves no label and, since
WRAM is not in the ROM image, cannot change output.

**Rule: Lab code never writes outside its declared ranges.** A test asserts the Lab sections do not
overlap any original section.

### 4.2 The piece sequencer — reuse, don't replace

The original already has a deterministic piece path: when `hMultiplayer != 0` (or a demo is running)
it reads pieces sequentially from **`wRandomness`, a 256-byte table at `$C300`**, indexed by
`hRandomnessPtrLo` (`$FFB0`), wrapping at 256 (`docs/research.md` §3.5).

**Seeded sequences, drought injection, scripted drills and VS-parity all reduce to: fill 256 bytes
and force that branch.** No new generator, no hook in `SpawnNewTetromino`.

> **SUPERSEDED for SPS, 2026-08-20.** Reverse engineering the community's seeded ROM
> (`docs/existing-hacks.md` §4) showed it hooks the entropy source instead: it replaces the
> `ldh a, [rDIV]` read with a call to a 16-bit LFSR. **We adopt that approach and that exact LFSR**,
> because identical seeds must yield identical sequences across both ROMs — for a fairness feature,
> interoperability beats elegance. The `wRandomness` route stays valid for *drought injection and
> scripted drills*, where compatibility does not apply and a fully controlled sequence is wanted.

Two caveats to handle explicitly:
* The table **wraps at 256 pieces**; a 100-line run is roughly 250 pieces, so wrap is reachable.
  Either refill the table on wrap (needs a small hook) or accept repetition and document it.
  **Resolve this early — it is open question #3 in `docs/research.md` §8.**
* The attract demo uses the same table, so it must be restored when leaving a trainer.

### 4.3 SRAM (`$A000–$BFFF`, 8 KB)

| Range | Contents |
| --- | --- |
| `$A000–$A00F` | Magic + version + checksum. **Refuse to load mismatched saves; re-initialise instead.** |
| `$A010–$A0FF` | Persistent Lab config (last trainer, level, heart flag, DAS values, seed) |
| `$A100–$A7FF` | Savestate slots (a 10×18 board snapshot is 180 B, so ~8 slots with metadata is comfortable) |
| `$A800–$BFFF` | Reserved |

SRAM must be enabled (`$0000 = $0A`) before access and disabled after. Never leave it enabled across
a frame boundary — an unexpected reset with SRAM enabled is the classic save-corruption path.

### 4.4 VBlank budget — the real scarcity

The original VBlank handler is already near-full: 18 unrolled row-shift calls, OAM DMA, the B-type
scoring screen, the highscore tilemap and a conditional two-map score render, in ~1.09 ms
(`docs/research.md` §3.8).

**Rules for all Lab rendering:**

1. Lab HUD rendering runs from **one hook at the end of the original VBlank handler**, never from
   multiple places.
2. Render from a **dirty-flag queue**: main-loop code stages tile writes into a small WRAM buffer
   and sets a flag; VBlank drains at most **N tiles per frame** (start with N = 16 and measure).
3. **Never** do arithmetic in VBlank. BCD conversion, timer formatting and statistics all happen in
   the main loop.
4. Any feature that cannot fit this budget is redesigned or dropped — **it does not get to steal
   time from the original render path**, because that would change original timing.

Prefer **sprites over tilemap writes** for small indicators (DAS charge, input display): OAM is
already DMA'd every frame, so an extra sprite costs nothing in VBlank. The 10-sprites-per-scanline
limit is the constraint there, not time.

---

## 5. Build system

`python3 build.py` and nothing else. No `make`, no `gcc`, no system-wide installs.

```
python3 build.py                 # default: LAB=1, MBC1, 64 KB, SRAM
python3 build.py --original      # LAB=0: reproduce v1.1 byte-exact  (the regression test)
python3 build.py --patch         # additionally emit build/tetrislab.bps  (needs a user ROM)
python3 build.py --freespace     # print per-bank free bytes from the link map
```

Stages:

1. **Toolchain** — `tools/rgbds.py` downloads the pinned RGBDS v0.6.1 Linux/macOS tarball, verifies
   its SHA-256 against a checked-in constant, and extracts it into `build/toolchain/`. Never touches
   the system. If a matching `rgbasm` is already on `PATH`, use it and print which.
2. **Graphics** — `tools/gfx.py` runs `rgbgfx` and **truncates each output to an explicitly declared
   expected byte count**, asserting the result. (Both `kaspermeerts` and `meithecatte` need this;
   `kaspermeerts` fails to build without it, and getting it wrong produces a confusing
   "section overlaps" link error. `docs/research.md` §6.)
3. **Assemble** — `rgbasm` per translation unit, with `-D LAB=1` / `-D LAB=0` selecting hooks.
4. **Link** — `rgblink -m build/tetris.map -n build/tetris.sym`. **Both outputs are mandatory**:
   the map drives free-space accounting, the sym file drives symbolic debugging and the test harness.
5. **Fix** — `rgbfix` sets cartridge type, ROM/RAM size and checksums.
6. **Verify** — always: hash the ROM; assert banks 0–1 differ from the reference only at declared
   hook addresses; print per-bank free space.
7. **Patch** (opt-in) — `--patch` emits `build/tetrislab.bps` and verifies it round-trips. The
   source is our own byte-exact rebuild of the stock ROM, so cutting a release needs no copy of
   it; only *using* a release does.

Every build prints a budget line, because on this target space is a first-class concern:

```
free space:
  ROM0 bank #0     0 bytes   (51 reserved for the header)
  ROMX bank #1     40 bytes
  ROMX bank #2     14915 bytes
  WRAM0 bank #0    691 bytes
  HRAM bank #0     0 bytes
```

**Bank 0 is full.** The 51 bytes the linker reports empty are the Nintendo logo
(`$0104-$0133`) and the header checksums (`$014D-$014F`), which `rgbfix` fills
after linking — the boot ROM refuses to run a cartridge whose logo does not
match, so writing there bricks the ROM. `--freespace` excludes them rather than
inviting the mistake. Everything bank 0 gained is in reclaimed `ds` padding
(`src/hooks/hooks.inc`), and there is none of that left either.

---

## 6. Testing strategy

Four layers, cheapest first.

### Layer 1 — Byte-exactness (the foundation)

```
python3 build.py --original  &&  sha1sum == 74591cc9501af93873f9a5d3eb12da12c0723bbc
```

**This test must pass on every commit, forever.** It is the mechanical guarantee that D1's promise —
"the gameplay is the original machine code" — is still true. If it fails, the change is wrong,
regardless of how good it looks.

### Layer 2 — Original-bank diff

Build with `LAB=1`, diff banks 0–1 against the reference, and assert the set of differing byte
addresses equals exactly the declared hook table. Catches accidental drift into original code —
the failure mode most likely to silently change gameplay.

### Layer 3 — Static/link assertions

* Lab WRAM sections do not overlap original sections.
* Per-bank free space stays above a floor (fail the build before the linker does, with a better
  message).
* Expected graphics sizes match.
* Every symbol the test harness needs exists in the `.sym` file (TetrisGYM does exactly this in
  `tests/src/labels.rs`).

### Layer 4 — Behavioural tests in a headless emulator

Model this on TetrisGYM's `tests/` crate: load the built ROM, parse the `.sym` file, run frames,
inject inputs, assert on memory.

* **Emulator choice:** prefer a scriptable, embeddable core over a GUI. **SameBoy** is the accuracy
  reference (passes mooneye-gb, blargg, Wilbert Pol suites; >99.9 % on ~2 800 commercial games) and
  is embeddable as a C library. A pure-Python core would keep the "stdlib only" promise but is slow
  and less accurate. **Recommendation: define a thin `tools/emu.py` interface, start with whatever is
  easiest to drive from CI, and keep the interface narrow so the core can be swapped.**
  Decide this in Milestone 1 and record it as an ADR.
* **The tests that matter most are timing tests**, because timing *is* the product:
  * gravity frames per level match the table at `$1B06` for all 21 levels;
  * DAS is 23 frames initial / 9 autorepeat;
  * ARE is 2 frames; line-clear delay is 93 frames;
  * a seeded run produces a byte-identical piece sequence twice;
  * enabling a trainer does not change any of the above.
* **Interactive debugging** (not CI): **BGB** and **Emulicious** both consume `rgblink`'s `.sym`
  output and give full symbolic breakpoints, VRAM viewers and cycle counters. Document the workflow
  in the README; it is how contributors will actually work.

### Hardware validation

Automated tests cannot prove the ROM runs on a DMG. Before every release: flash to an **EverDrive
GB** or **EZ-Flash Junior**, verify boot, gameplay, and **SRAM persistence across a power cycle**.
Test on DMG, Game Boy Pocket and Game Boy Color. This is a manual checklist item in
`docs/roadmap.md`, not a CI job.

---

## 7. Emulator and hardware strategy

| Target | Support level | Notes |
| --- | --- | --- |
| SameBoy, BGB, Emulicious, mGBA | **Fully supported, tested** | MBC1 is universally and correctly implemented |
| EverDrive GB X3/X5/X7, EZ-Flash Junior | **Fully supported, manually verified per release** | Both handle MBC1 + SRAM saving |
| Analogue Pocket, MiSTer FPGA | **Expected to work, verify opportunistically** | MBC1 is standard |
| DMG / GBP / GBC via flash cart | **Supported** | The real-hardware story |
| **An original retail Tetris cartridge** | **Not supported — and could never be** | It is **mask ROM**: unwritable by construction. *No* modified ROM runs on a retail cart, so this is not a cost of D5. |
| DIY repro cartridge | **Supported, with a caveat** | D5 raises the bar from "a 32 KB flash chip in a donor cart" to "a board with an MBC1 and battery SRAM". **This is the only place D5 has a real hardware cost.** |
| Game Boy Color enhancement | **Out of scope** | Runs in DMG compatibility mode. Colourisation is not a training feature. |
| Super Game Boy | **Out of scope** | No borders, no SGB palettes. |

A **32 KB no-MBC "purist" build** — original ROM plus only the features that fit in ~400 bytes — is
a possible stretch goal, not a design constraint. Its audience is narrow: it would not run on a
retail cart either (mask ROM), only on a simple ROM-only repro board. Do not let it shape the main
architecture.

---

## 8. Extension model — adding a feature

1. Write the code in `src/lab/`. Keep it in bank 2 unless it must be reachable
   while bank 1 is mapped, in which case use bank 1's empty space (as
   `random.asm` does) or a bank-0 stub.
2. If it needs to run inside an original state, route that state's jump-table
   entry through `LabStateHook` and branch in `LabDispatch`.
3. **If it changes bytes in banks 0 or 1**, declare the range in
   `src/hooks/hooks.inc`, mirror it in `tests/test_expansion.py`, record it in
   `src/original/UPSTREAM.md`, and justify it in the PR. Those get extra review.
4. Add a behavioural test driving the ROM through `tools/emu.py`.
5. Update `README.md` and `docs/roadmap.md`.

**Prefer changing state over changing code.** Most features need no hook: set up
RAM and the tilemap before gameplay starts and let the untouched original run.

## 9. What this architecture deliberately does not do

* **No abstraction layer over the original game.** No "board API", no "piece API". The original's
  data structures (VRAM tilemap + WRAM shadow for the board, OAM for the active piece) *are* the
  interface. Wrapping them would cost bytes and cycles and hide the thing we are trying to preserve.
* **No scripting language, no config file format, no data-driven mode engine.** Modes are asm files.
  If we ever have twenty of them and the duplication hurts, revisit — with evidence.
* **No support for multiple ROM versions initially.** v1.1 only. Add v1.0 only if §7-A3 of
  `docs/community-research.md` shows the community needs it, and add it as a build flag, never as a
  parallel source tree.
* **No new gameplay mechanics.** Hold, hard drop, ghost pieces and SRS are out of scope by decision,
  not by omission (`docs/community-research.md` §5, rows 21–22).
