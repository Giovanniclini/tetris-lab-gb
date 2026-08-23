# Roadmap

**This file is the single source of truth for project status.** README and
CLAUDE.md point here rather than restating it, so there is one place to keep
current.

| Milestone | State |
| --- | --- |
| 0 — Reproduce the original ROM | **done** |
| 0.5 — Cartridge expansion (MBC1, 64 KB, SRAM) | **done** — the cartridge has SRAM; nothing writes to it yet |
| 1 — Level picker, hearts, instant restart | **done** — except SRAM persistence, see below |
| 2 — Core training features | **in progress** — SPS done; transition trainer next |
| 3 — Board control and information | not started |
| 4 — Replay, tooling and polish | not started |
| 5 — Hardware validation and 1.0 | not started |

**Released:** `v0.3.0`, 2026-08-22 — the rename, and everything the community
reported. Still an alpha, and still ahead of the Milestone 2 gate below. BPS
patch on [Releases](https://github.com/Giovanniclini/tetris-lab-gb/releases).

Outstanding across finished milestones:

* **SRAM persistence is not implemented.** The cartridge declares 8 KB of
  battery RAM (M0.5) but no code writes to it, so settings and high scores live
  in WRAM: they survive the soft reset, not a power cycle. M1 work item 4 was
  never done, and the milestone was marked complete without it.
* Booting on a real DMG/GBC via a flash cart — needs hardware nobody has yet.

Milestones are ordered by *risk retired per unit of effort*. Each has
acceptance criteria that are objectively checkable.

Two deviations from the original kickoff plan, both still standing:

* **M0.5 was inserted** to convert the cartridge to MBC1 before any feature.
  The original ROM has ~400 usable free bytes, so without it every feature was
  blocked. Doing it alone meant the riskiest structural change was validated
  while the ROM was otherwise byte-identical.
* **Feature order follows Game Boy community evidence, not TetrisGYM's.** SPS
  is Milestone 2's headline because the community has asked for it by name
  since 2022 (`docs/community-research.md` §6.2).

---

## Milestone 0 — Reproduce the original ROM

**Goal:** `git clone && python3 build.py --original` produces `Tetris (World) (Rev A)` byte-exactly,
on a machine with nothing but Python 3 and network access.

**Work**
0. **Before writing code:** catalogue the GBTetris Discord's existing-ROM channel and obtain the
   "more level starts + score digit + rocket skip" hack (`docs/community-research.md` §7 A7). We
   must be a clean superset of what people already use, and must not duplicate the local
   romhackers' work.
1. Vendor `vinheim3/tetris-gb-disasm` at a pinned commit into `src/original/`; record the SHA,
   licence and (initially empty) delta list in `src/original/UPSTREAM.md`.
2. `tools/rgbds.py`: download RGBDS v0.6.1, verify SHA-256, extract into `build/toolchain/`.
3. `tools/gfx.py`: PNG → 2bpp/1bpp with **explicit expected byte counts** and assertions.
4. `build.py`: assemble → link (emit `.map` **and** `.sym`) → `rgbfix`.
5. `tests/test_original.py`: assert the SHA-1.
6. CI: Linux + macOS, clean checkout, run the test.

**Acceptance criteria**
- [x] `python3 build.py --original` → SHA-1 `74591cc9501af93873f9a5d3eb12da12c0723bbc`
- [x] Works with **no** system-wide installation (no `make`, no `gcc`, no package manager)
- [x] `--freespace` prints per-bank free bytes parsed from the link map
- [x] Regression tests beyond the hash: cartridge header, the 21-entry gravity table at `$1B06`,
      and the DAS constants (23 initial / 9 autorepeat)
- [ ] CI is green on Linux and macOS from a clean checkout *(workflow committed, not yet run)*
- [ ] `build/tetris.sym` loads in BGB and shows named symbols *(needs a human with BGB)*
- [ ] The ROM boots and is playable in SameBoy *(needs a human)*

**Status 2026-08-20: essentially complete.** Verified locally from a clean checkout —
toolchain auto-fetched and SHA-256-verified, graphics regenerated, 4/4 tests passing. The
remaining boxes need a human in front of an emulator.

**Risks retired:** upstream buildability (already verified in research, but not yet reproducibly);
toolchain pinning; upstream issue #6.

---

## Milestone 0.5 — Cartridge expansion (no features yet)

**Goal:** the ROM is MBC1, 128 KB, with 8 KB battery SRAM — and **plays identically**.

**Work**
1. `rgbfix` cartridge type `$03`, ROM size 128 KB, RAM size 8 KB.
2. Reclaim bank-0 filler `$005B–$00FF` (165 B) as a section; add `FarCall` trampoline and
   `hCurrentBank` at `$FFFD`.
3. Split `src/original/include/wram.s` into named per-purpose sections so the linker reports real
   free space. **Must not change a single output byte.**
4. Declare empty Lab sections in banks 2–7 and the Lab WRAM/SRAM ranges.
5. `tests/test_original.py` grows Layer 2: diff banks 0–1 against the reference, assert the changed
   byte set equals the declared hook table (initially: the trampoline only).

**Acceptance criteria**
- [x] Banks 0–1 differ from the reference **only** at the declared, enumerated addresses
      (27 bytes: 22 trampoline + 3 header + 2 checksum), asserted by `tests/test_expansion.py`
- [x] `--original` still produces the byte-exact ROM (the `LAB=0` path is unaffected)
- [x] Cartridge is MBC1 + 8 KB battery SRAM; `--no-sram` variant also builds (D9)
- [x] Banks 2–3 exist with ~16 KB free each; Lab WRAM claimed from the verified gap
- [ ] `FarCall` into a stub in bank 2 and back works, verified in an emulator
      *(trampoline assembled and byte-checked; execution needs the M1 harness)*
- [ ] SRAM survives a power cycle on real hardware *(needs a flash cart)*
- [x] Gameplay is indistinguishable — verified in mGBA 0.10.5, 2026-08-20. The only observable
      difference was greyscale vs colour, which is emulator ROM-database recognition, not the ROM
      (`docs/research.md` §4.1a)
- [ ] Boots on DMG, GBP, GBC, SameBoy, BGB, Emulicious

**Status 2026-08-20: structurally complete, awaiting behavioural verification.**

**ROM size revised to 64 KB (4 banks), not the 128 KB in D5.** Size the cartridge to what we
actually use: banks 2–3 give ~32 KB of Lab space against a current usage of a few dozen bytes, and
a smaller ROM is a cheaper cartridge — which matters, because the community intends to have carts
produced (`docs/community-research.md` §3.5.7). Growing later is a one-line change.

**Risks retired:** the single largest structural risk in the project. If MBC1 conversion breaks
something subtle, we find out here — while the ROM is otherwise unmodified and the cause is
unambiguous.

---

> **REORIENTED 2026-08-20.** Channel archaeology (`docs/community-research.md` §3.5) replaced
> inference with the community's own five-year-old, repeatedly-stated product definition:
>
> > *"a competition rom with **A-M starts and SPS** would be the top of the list"* — nells
>
> M1 and M2 below now target exactly that. Two consequences:
>
> * **SPS is the one headline feature nobody has finished in five years**, and it is unusually cheap
>   on Game Boy (`docs/research.md` §3.5). That is the wedge.
> * **KLM already provides A–M level starts and score uncap, and a separate ROM already provides the
>   40-line timer.** We must **match KLM or we ship a downgrade**, and we should **integrate rather
>   than reinvent** the timer. Our differentiator is not features — it is being the first
>   *buildable, tested, maintainable* base, which is precisely what broke when Tolstoj tried to
>   restructure KLM (§3.5.8).

## Milestone 1 — First Lab functionality: level select + instant restart

**Goal:** the smallest change that is *already useful*, and that proves the whole hook/menu/bank
architecture end to end.

Chosen because these are ranked #2 and #3 in `docs/community-research.md` §6, cost almost nothing
(both are near-trivial given the original's structure), and exercise every architectural element:
a menu screen in an unused `hGameState` slot, a hook, banked code, and Lab WRAM.

**They are also not a convenience feature.** Measured in `docs/research.md` §3.7: the original makes
only levels 0–9 selectable; heart levels are armed by an undocumented `Down`+`Start` at the *title
screen*, two screens before the level menu, with no feedback until a `♥` appears; **effective level
20 is unreachable from the menu at all** (`min(level + 10, 20)` with a menu cap of 9 yields 19); and
every reset costs ~4.2 s of unskippable copyright screen plus four menu screens. Returning to a
chosen practice speed takes roughly 15 seconds and a remembered button combination. This milestone
is the difference between one attempt and twenty.

**Work**
1. Lab menu on an unused `hGameState` jump-table slot, reachable from the title screen.
2. **Start on any level 0–22 (0–9, A–M) with a heart-level toggle** — write `hATypeLevel` and the
   gravity reload value from the table at `$1B06`.
   **Scope restored to A–M**: KLM has been reverse engineered (`docs/existing-hacks.md` §3), so L
   and M are exactly specified — extend the table to 23 entries with L = `$01` (2 frames/row) and
   M = `$00` (1 frame/row, the engine's hard ceiling). The score multiplier `(level+1) × base`
   extends with no table change. Match KLM exactly; verify L scores 26 400 per Tetris.
3. **Instant restart**: retarget the existing `A+B+Select+Start` soft reset to restart the current
   trainer with identical settings instead of rebooting.
4. Lab config persisted to SRAM; restored on boot.
5. Headless emulator harness (`tools/emu.py`) + first behavioural tests. **Record the emulator choice
   as an ADR** (`docs/decisions/`).

**Acceptance criteria**
- [x] Can start A-Type on any level 0–22 via a picker beside the grid, hearts toggled with Select
- [x] Gravity at each selected level matches the table **exactly**, asserted for all 23 levels
- [x] Instant restart returns to a fresh game with identical settings in under 1 second (measured: 0.17 s)
- [ ] Settings survive a power cycle on real hardware
- [x] DAS constants verified unchanged; ARE and line-clear delay still to assert behaviourally
- [x] ~~Hook count ≤ 4~~ — retired, `docs/decisions/0008`: every hook declared, diff-tested and justified instead
- [x] `--original` still byte-exact

---

**Status 2026-08-20: complete.** Level picker reaching A–M, hearts on Select
with an indicator, instant restart from a game and everything downstream of it,
and a headless emulator harness. Verified in an emulator and by hand.

---

## Milestone 2 — Core training features

**Goal:** the product becomes genuinely useful to a CTWC-GB competitor — and specifically, reaches
the bar the GBTetris Discord named for a physical cart run: *"SPS + extended level select +
whatever else"* (`docs/community-research.md` §3.4).

**Status 2026-08-20: SPS complete.** The community's LFSR, interoperable and
verified against their ROM (`docs/existing-hacks.md` §4), with seed entry beside
the level picker. A seed of `$0000` means "no seed", so SPS is off and pieces
come from `rDIV` as they always did.

**Status 2026-08-21:** levels A–M have their own high-score slots, so a score is
filed and shown under the level it was played at (`docs/decisions/0006`).

**Status 2026-08-21:** the A-TYPE/B-TYPE screen is now the Lab menu, modelled on
TetrisGYM's list, and carries the first trainer — TRANSITION
(`docs/decisions/0007`).

**Status 2026-08-22:** the score passes 999 999 — the clamp is a carry handler
now, and a seventh digit is drawn into the panel's left edge. High score entries
carry it too, in the dotted gap between the name and the score, and rank by it:
the original compares three bytes, so 1 000 050 stored as 000050 would have lost
to 999 999. Only the comparison is ours — the shift, the name and the display
stay the original's. No new hooks.

**Status 2026-08-22:** the rocket scene is skipped whole — the 2.4-second wait
and the twenty-odd seconds after it, at exactly the scores a good session
produces. Every score now reaches the game over screen in two frames, by the
path the original already uses for scores under 100 000. This replaces the
fix a day earlier that made the rocket fire past a million: correct, and dead
the moment the scene stopped playing.

**Status 2026-08-22:** pushdown no longer applies at L and M, where it made the
piece slower rather than faster. Reported by Tolstoj; the drop points go with
it, by Giovanni's call — no push, nothing to reward.

Work follows the revised list in `docs/community-research.md` §6.2:

1. **SPS — standardised same piece sequence** (§6.2 #1). *The headline feature.* Design is now
   settled by reverse engineering the existing seeded ROM (`docs/existing-hacks.md` §4):
   **replace the `ldh a,[rDIV]` read in the piece generator with the community's exact 16-bit
   LFSR**, state in HRAM, result read as a byte. Apply the same substitution to the B-type garbage
   generator. Everything downstream — the ×4 counting loop, the OR-rejection retry, the biased
   distribution — stays untouched.
   **Use their LFSR bit-for-bit, not a better one.** Identical seeds must produce identical
   sequences across both ROMs, because interoperability *is* the feature for a fairness mechanism.
   **Guard the degenerate seed:** `$0000` has period 1 and always returns zero.
   The 256-piece wrap question (`docs/research.md` §8 #3) is moot under this design.
2. **Match KLM: level starts A–M (10–22) with an extended gravity and scoring table, plus score
   uncap** (§6.2 #2, #4). Non-negotiable — KLM is the de-facto standard and anything less is a
   downgrade. Verify L = 2 frames/row and 26 400 per Tetris against the KLM ROM itself.
3. **Transition trainer** (§6.2 #6) — start near the end of a 9-start's 100-line grind. **Contact
   mathmaster13 first** (§7 A13): a transition-trainer patch was already in progress as of 2026-05.
   Set
   `hNumLinesCompletedBCD` and `hATypeLinesThresholdToPassForNextLevel` at load time; no gameplay
   hook. Named as the most annoying thing in a practitioner's routine.
3. **Floor mode / preset boards / garbage-height setup** (§6.1 #5). Tilemap writes at
   `LOAD_PLAYFIELD` time.
4. **Low stack** (§6.1 #7) — height limit, game over above it.
5. **Frame-accurate timer + 40-line sprint mode** (§6.2 #3). **A8 resolved: this is the live
   tournament qualification format and one of the two most-used ROMs — the earlier demotion was
   wrong.** A working implementation already exists (Pascal/Tolstoj), so **integrate and
   standardise**. Get its exact start/stop semantics first (§7 A15) — Tolstoj: *"stops the timer one
   frame after the piece locks"* — and note an older revision's hex frame counter ran to `$3C`,
   making historical times differ by ~1.7 s. Adopt Pascal's zero-friction design: boot straight to
   the menu, no configurable settings, one button to restart.
6. **Drought / piece-bias injection** — nearly free once (1) exists.
7. **VS-style garbage / dig trainer** (§6.1 #10). Original VS rules: single aligned hole, 1 line per
   double / 2 per triple / 4 per Tetris.

**Acceptance criteria**
- [x] **SPS: the same seed produces a byte-identical piece sequence across two runs**, asserted in tests
- [ ] **Level starts A–M match the KLM ROM's speed and scoring exactly**, verified against KLM itself
- [ ] Sprint timer agrees with the existing qual ROM to the frame on the same inputs
- [x] Transition trainer drops the player at a chosen line count with correct level, gravity and score state
- [ ] 40-line sprint: timer starts on first piece, stops on the 40th line, accurate to ±0 frames
      (verified against an emulator frame count, not a wall clock)
- [ ] Seeded sequences match the original's 2-player behaviour (same-pieces parity)
- [ ] Behaviour at the 256-piece boundary is defined, tested and documented
- [ ] Garbage generation matches the documented VS rules
- [ ] VBlank budget measured and documented; HUD rendering stays within it
- [ ] All timing tests from M1 still pass with every trainer enabled
- [x] `--original` still byte-exact (hook count cap retired — `docs/decisions/0008`)

**Ship a public alpha here** (BPS patch, release notes, README feature table) and take it to the
GBTetris Discord. Real feedback should reorder everything after this point.

---

## Milestone 3 — Board control and information

**Goal:** the player can author and repeat an exact scenario, and can see what the original hides.

**Work** — top-10 items #7, #8, #9, #10:
1. **Savestates** in SRAM (~8 slots), save/load during pause.
2. **Board editor** — cursor, draw/erase, current+next piece selection.
3. **Uncapped score and extended line counter**.
4. **DAS delay control and an on-screen DAS charge indicator** (sprite-based to stay off the VBlank
   budget).
4b. **Hz / tap-rate counter** (§6.1 #6) — explicitly requested; pull forward to M2 if §7 A8 demotes
   the sprint timer.
5. **Piece statistics and drought counter**, presented against Game Boy's *actual* biased
   distribution (L 10.7 %, J/I/Z 13.7 %, O/S/T 16.1 %).

**Acceptance criteria**
- [ ] A board can be authored, saved, power-cycled and reloaded identically
- [ ] The DAS indicator matches the real counter frame-for-frame, verified in an emulator trace
- [ ] Score displays correctly past 999 999 without corrupting the original scoring path
- [ ] Statistics match a known seeded sequence exactly
- [ ] Sprite usage stays within the 10-per-scanline limit in all HUD configurations
- [ ] `--original` still byte-exact

---

## Milestone 4 — Replay, tooling and polish

**Goal:** review and share, plus the long-tail challenge modes.

**Work**
1. **Input recording and playback**, building on the ROM's dormant `RecordDemo` /`$FFE9` machinery
   (`docs/research.md` §3.6) — a genuine Game Boy-specific advantage.
2. Input display (sprite-based).
3. Pace indicator against 300 000 / 999 999 targets.
4. Challenge modes: fixed-speed marathon, invisible, low-stack, crunch.
5. B-Type Level 9 / High 5 quick-drill.
6. Configurable line-clear delay for faster drilling.

**Acceptance criteria**
- [ ] A recorded input sequence replays to a bit-identical final board and score
- [ ] Replays survive a power cycle
- [ ] Each challenge mode has a behavioural test
- [ ] Documentation covers every mode with a screenshot

---

## Milestone 5 — Hardware validation and 1.0

**Goal:** a release the community can trust in a tournament.

**Work**
1. Full hardware matrix: DMG, Game Boy Pocket, Game Boy Color, Super Game Boy (compatibility only),
   Analogue Pocket, MiSTer — on EverDrive GB and EZ-Flash Junior.
2. SRAM corruption testing: power-cut during save; battery-dead behaviour; version-mismatch handling.
3. Emulator matrix: SameBoy, BGB, Emulicious, mGBA.
3b. **Verify Game Boy Color auto-palette on real hardware.** The expanded ROM keeps every input to
   the CGB boot ROM's palette lookup byte-identical (`docs/research.md` §4.1a), so it should
   colourise exactly like the original — but that is analysis, not observation. Emulators that key
   colour off a ROM database rather than the boot ROM (mGBA does) will show greyscale; document it
   so users do not report it as a bug.
4. Timing audit: re-verify every original constant against the reference build.
5. Documentation pass; BPS release pipeline; `docs/decisions/` complete.
6. **Optional stretch:** a 32 KB no-MBC "purist" build for reflashed original cartridges.

**Acceptance criteria**
- [ ] Verified working on at least DMG + GBC on at least two flash carts
- [ ] SRAM survives adversarial power cycling; a mismatched save re-initialises rather than corrupting
- [ ] No gameplay-timing deviation from the reference ROM in any configuration
- [ ] Release contains a **BPS patch only** — no `.gb` artifact anywhere
- [ ] README documents ROM requirements, hashes and the flash-cart requirement plainly

---

## Continuous, from Milestone 0 onward

* **Every commit:** `--original` byte-exactness + the original-bank hook diff. Non-negotiable.
* **Every PR that adds a hook:** extra review, and an update to the expected hook table.
* **Every significant decision:** an ADR in `docs/decisions/`.
* **Every milestone:** re-read `docs/community-research.md` §7 and act on the open research
  actions — especially **A1, joining the GBTetris Discord.** The feature ranking beyond Milestone 2
  is the least certain part of this plan, and talking to 27 tournament players would resolve more of
  it than any amount of further desk research.

---

## Sequencing rationale

| Milestone | Risk it retires |
| --- | --- |
| M0 | "Can we even build this reproducibly?" |
| M0.5 | "Does the cartridge expansion break the game?" — the biggest structural unknown |
| M1 | "Does the hook/bank/menu architecture actually work?" — proved with a useful feature, not a stub |
| M2 | "Is this useful to a real competitor?" — answered by shipping and asking |
| M3–M4 | Depth, guided by M2 feedback rather than by this document |
| M5 | "Can it be trusted on real hardware in a tournament?" |
