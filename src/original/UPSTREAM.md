# Vendored disassembly — provenance

This directory is a **verbatim copy** of the `disasm/` subtree of an upstream
Game Boy Tetris disassembly. It is vendored, **not forked**.

| | |
| --- | --- |
| Upstream | <https://github.com/vinheim3/tetris-gb-disasm> |
| Pinned commit | `af54544fe292464055dc1d32490e48c4f998c9d9` (2023-01-19) |
| Licence | MIT — Copyright © 2023 Daniel Jianoran (see `LICENSE`) |
| Target ROM | Tetris (World) (Rev A), "v1.1" |
| SHA-1 | `74591cc9501af93873f9a5d3eb12da12c0723bbc` |
| MD5 | `982ed5d2b12a0377eb14bcdc4123744e` |
| Coverage | 100 % — upstream `coverage.txt` reports 0 bytes remaining |

Note that the upstream MIT licence covers the author's annotation and
organisation work. It cannot grant rights over the underlying game content,
which remains copyrighted. See `docs/research.md` §7.

## Local deviations from upstream

Eleven, all minimal. `build.py --original` still reproduces the stock ROM byte-exactly.

Only three categories of deviation are ever permitted, and every one must be
listed in the table below with a justification (see `docs/architecture.md` §3.1):

1. **Toolchain migration** — syntax required by the pinned RGBDS version.
   Must not change a single output byte.
2. **Section splitting** — e.g. splitting the monolithic `include/wram.s` into
   named per-purpose sections so the linker reports real free space.
   Must not change a single output byte.
3. **Hook insertion points** — declared in `src/hooks/hooks.inc`. These *do*
   change bytes, and each is enumerated and counted by `tests/`.

| # | File | Change | Category | Why | Bytes changed |
| --- | --- | --- | --- | --- | --- |
| 1 | `code/bank_000.s` | `IF LAB` include of `hooks/trampoline.inc` immediately before `ds $100-@, $ff` | 3 (hook) | The entry-point padding at `$00DA-$00FF` is the only free space in bank 0. The far-call trampoline must live in bank 0 because the caller may execute from any bank. | 22 of 38 available, `$00DA-$00EF`. Zero when `LAB=0`. |
| 2 | `include/wram.s` | Split the monolithic `$C000-$DFFC` section, starting a new `"WRAM Audio"` section at `$DF70` | 2 (section split) | Upstream declares all of WRAM as one section, so the linker cannot see the 2062-byte gap at `$D762-$DF6F`. No label moves. (The game does reach the first 351 bytes of that gap - its high score indexing runs off the end of the table for levels above the grid - which is why the Lab continues the table there rather than treating the space as free. See `docs/decisions/0006`.) | **0** — WRAM is not in the ROM image |
| 3 | `code/bank_000.s` | `IF LAB` include of `lab/gravity.inc` into the `ds $28-@, $ff` padding, and the `ld hl, .framesData` operand redirected to it | 3 (hook) | Levels L (21) and M (22) need a 23-entry gravity table. Placing it in reclaimed padding and redirecting the pointer avoids shifting bank 0. KLM achieves the same feature by relocating the table, which moves every byte after it — 20 870 bytes changed versus our 25. | 23 (table) + 2 (pointer operand). Zero when `LAB=0`. |
| 4 | `code/inGameFlow.s` | `IF LAB` turns the level-up cap's `ret z` into `ret nc` | 3 (hook) | Stock stops levelling only on *equality* with `$14`, which is fine when 20 is the highest level there is. With L and M selectable, 21 never equals 20, so it keeps climbing past the end of the gravity table into code. `ret nc` stops at 20 or above — identical for every level the original can reach, and an L or M start never transitions. **KLM makes the same one-byte change** (`cp $14 / ret nc` at its `$244D`); an earlier reading here reported a bug KLM does not have. | 1. Zero when `LAB=0`. |
| 5 | `code/bank_000.s` | `IF LAB` swaps two entries of `ProcessGameState`'s jump table (`$10` A-type select init, `$11` main) for `LabStateHook` | 3 (hook) | Routes the level-select screen through Lab code, which runs its own logic and then chains to the original handler. The handlers themselves are unmodified. | 4 (two `dw` entries). Zero when `LAB=0`. |

| 6 | `code/bank_000.s` | `IF LAB` redirects the `jp z, Reset` inside `InGameCheckResetAndPause` to `LabResetStub`, and adds the stub to the `ds $40-@, $ff` padding | 3 (hook) | Instant restart. This is the reset check that fires while gameplay is ticking. | 2 (operand) + 8 (stub). Zero when `LAB=0`. |
| 7 | `code/bank_000.s` | `IF LAB` turns MainLoop's `jp z, Reset` into `call z, LabResetStub` | 3 (hook) | The ROM has **two** soft-reset checks. The in-game one goes quiet during the restart's own init frames, and this one would reboot us a moment later. `call` so the Lab can decline. | 3. Zero when `LAB=0`. |
| 8 | `code/bank_000.s` | `IF LAB` routes the `$04` jump-table entry (end-of-game screen) through `LabStateHook` | 3 (hook) | That handler treats Start as "back to the level select", and Start is part of the reset combination - so by the time either soft-reset check runs the state has moved on and we would reboot. Catching it here is what makes "top out, go again" work. | 2. Zero when `LAB=0`. |
| 9 | `code/inGameFlow.s`, `code/bank_000.s` | `IF LAB` replaces `ldh a, [rDIV] / ld b, a` with `call LabRandom` at the piece generator and at B-type's garbage draw | 3 (hook) | SPS. Three bytes for three, so nothing shifts. `LabRandom` returns the value in B exactly as those instructions did, and returns `rDIV` unchanged when SPS is off, so everything downstream — the counting loop, the OR-rejection retry and its bias — is untouched. | 3 + 3. Zero when `LAB=0`. |
| 10 | `code/bank_000.s` | `IF LAB` routes the `$15` jump-table entry (high score name entry) through `LabStateHook` | 3 (hook) | So the reset combination restarts the drill from the name entry screen instead of rebooting. Abandoning the score is the point — when you are drilling you want another go, not a leaderboard entry. | 2. Zero when `LAB=0`. |
| 11 | `code/bank_000.s` | `IF LAB` routes the `$0A` jump-table entry (in-game init) through `LabStateHook` | 3 (hook) | Loads the configured seed into the LFSR at the start of every game. Without it an instant restart would continue the sequence rather than repeat it, which defeats the point of a seed. | 2. Zero when `LAB=0`. |

## What was not vendored

Upstream's `web/` visualiser, `tools/`, `coverage.txt` and `README.md` are not
needed to build and were left out. Fetch them from upstream if useful — the
visualiser in particular is a handy reference for screen layouts and sprites.
| 13 | `code/bank_000.s` | `IF LAB` routes the `$00` jump-table entry (in-game main) through `LabStateHook` | 3 (hook) | The one per-frame gameplay hook. Trainers that must act while a game runs all land here rather than adding a hook each; the transition trainer needs it because the original's in-game init clears the line count after any earlier hook could set it. | 2. Zero when `LAB=0`. |
| 15 | `code/bank_000.s` | `IF LAB` routes the `$24` jump-table entry (copyright screen) through `LabStateHook`, which goes straight to the title init | 3 (hook) | 8.5 s before the menu on every boot of a ROM whose point is that you restart it constantly. Its only lasting effect is copying `DemoPieces` into `wDemoOrMultiplayerPieces`, which only the attract demo reads — 2-player shuffles its own table into it at `$068C`, and the tile data comes from `$06` either way. Boot to the menu: 9.8 s → 1.3 s. | 2. Zero when `LAB=0`. |
| 16 | `code/bank_000.s` | `IF LAB` routes the `$06`, `$07` and `$08` jump-table entries through `LabStateHook` | 3 (hook) | The title screen becomes the Lab menu. It has to be **this** state: `SerialFunc0_titleScreen` (`$0078`) only assigns a multiplayer role while `hGameState` is `$07`, and bounces the game back to the title from anywhere else — so the menu must also keep sending the passive ping the screen it replaced was sending. `$08` is where B on a level select goes, and would draw the A-TYPE/B-TYPE screen the menu replaced; it is sent back to the menu instead. `$06` draws the menu in place of the title, so the original never appears even for a frame — its clears, walls and floor are transcribed, because the falling piece collides against the buffer they are written into. See `docs/decisions/0007`. | 6. Zero when `LAB=0`. |
| 17 | `lab/random.asm` | `IF LAB` adds a 7-byte thunk in bank 1's empty gap at `$6430` | 2 (new section in a gap) | `LoadAsciiAndMenuScreenGfx` is in bank 0 but reads `Gfx_Ascii` from bank 1 (`$415F`), so it cannot be called while bank 2 is mapped — that address holds Lab code, and bank-2 code must not switch banks itself (ADR 0001). The menu far-calls this to load its tileset. Without it the level select drew the title screen's tiles as garbage. | 7 of 32 available. Zero when `LAB=0`. |
| 19 | `code/bank_000.s` | `IF LAB` replaces the 999 999 clamp at `$0178` with `jp LabScoreCarry` | 3 (hook) | Three BCD bytes hold six digits, and the clamp pins them all to `$99` on carry-out to stop them wrapping to zero — the ceiling of the storage, not a rule. The handler keeps the carry as a seventh digit instead. The community competes on KLM's uncapped score, and `docs/community-research.md` calls matching it the bare minimum. Three bytes for six; the rest is left as it was and is unreachable. | 3. Zero when `LAB=0`. |
| 20 | `code/bank_000.s`, `code/inGameFlow.s` | `IF LAB` draws the score at `+$6e` instead of `+$6d`, at all four call sites | 3 (hook) | The original leaves column 19 blank and ends the score at 18. Moving it one cell right uses that space, frees column 13 for the seventh digit, and means the number does not shift sideways when it passes a million. One byte of the operand each time — screens 0 and 1, twice over. | 4. Zero when `LAB=0`. |
| 21 | `code/bank_000.s` | `IF LAB` routes jump-table entry `$34` through `LabStateHook` | 2 (hook) | The rocket scene and the 2.4-second wait in front of it are 20+ seconds between topping out and playing again. A trainer wants the drill back. The Lab sends the state to the plain game over screen — where the original already sends every score that earns no rocket, so the path is its own. | 2. Zero when `LAB=0`. |
