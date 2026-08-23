# Reverse engineering the community's ROM hacks

**Status:** 2026-08-20. Derived by applying the patches pinned in the GBTetris Discord's
`#romhacks-modify` channel to our own byte-exact reference build and diffing the result.

**No ROM or patch data is stored in this repository.** The patches were analysed locally; only
findings are recorded here.

---

## 1. Method

Every community hack is a UPS or BPS patch against **Tetris (World) (Rev A)**, and
`build.py --original` reproduces that ROM byte-exactly. So:

```
build.py --original  →  reference ROM  →  apply community patch  →  diff  →  map to symbols
```

`tools/patch.py` implements both patch formats; `tools/analyze_hack.py` does the diff and maps each
changed run to the nearest preceding symbol from `rgblink`'s `.sym` output.

```
python3 build.py --original
python3 tools/analyze_hack.py /path/to/patch.ups
```

**Every one of the seven patches declares source CRC `46DF91AD`** — byte-for-byte our reference
build. That is independent confirmation of two things: v1.1 is definitively the community's base
(closing §7 A3 for good), and our build is exactly the ROM every community hack is built on.

## 2. Inventory

| Patch | Format | Target CRC | Changed | What it is |
| --- | --- | --- | --- | --- |
| `L-and-pushdown-fixed-2.ups` | UPS | `11261002` | 20 870 B / 80 regions | **The KLM ROM** — level K/L/M starts, score uncap, pushdown fix |
| `seeded.ups` | UPS | `6895B5AE` | 16 127 B / 14 regions | **The SPS ROM** — deterministic piece sequences |
| `sprint-mode-40-lines.bps` | BPS | `C452417C` | 12 562 B / 6 regions | 40-line sprint with built-in timer |
| `sprint-mode-30-lines.bps` | BPS | `EEFF38DD` | 12 562 B / 6 regions | 30-line variant (superseded) |
| `tetris_ctec_gb_qual_2024.bps` | BPS | `D568AE87` | 12 545 B / 9 regions | CTEC 2024 qualification ROM |
| `Tetris_ctec-2025-qual-v3.bps` | BPS | `F32864D1` | 29 533 B / 21 regions | CTEC 2025 qualification ROM |
| `tetris-patch-tp-v2.ups` | UPS | `6C0D0D44` | 1 182 B / 61 regions | Small surgical patch (score/pushdown related) |

**All seven are 32 768 bytes with an unchanged ROM-ONLY header.** Every hack in circulation is
squeezed into the stock cartridge with no mapper — which is precisely why none of them can be a
full Lab, and why our Milestone 0.5 expansion matters.

## 3. KLM — level K/L/M

### 3.1 The gravity table is relocated and extended

Stock has 21 entries (levels 0–20) at `$1B06`, immediately followed by code. KLM needed two more, so
it **moved the table back 21 bytes to `$1AF1`** and extended it to 23 entries.

| Level | Display | Stored | Frames/row | Rows/sec |
| --- | --- | --- | --- | --- |
| 0–20 | `0`–`K` | *identical to stock* | 53 … 3 | 1.13 … 19.91 |
| **21** | **`L`** | `$01` | **2** | 29.86 |
| **22** | **`M`** | `$00` | **1** | 59.73 |

**M is the hard ceiling of the gravity mechanism, not an arbitrary choice.** The counter reloads
with `stored + 1` frames; `$00` means one row per frame, which is the fastest the engine can express.
There is no N.

This confirms the community's own figures exactly: M-J's *"L is 2 frames/row compared to level 20's
3"*, and *"26400 for tetris"* on L, which is `(21 + 1) × 1200` — the score multiplier extends
naturally with no table change.

### 3.2 ~~A bug: the level-up cap was not raised~~ — WRONG, retracted

**[RETRACTED 2026-08-21. KLM does not have this bug. The claim was published in
the v0.1.0 and v0.2.0 release notes and reported to Tolstoj; both are corrected.]**

The original stops levelling only on *equality* with `$14`:

```asm
    cp   $14
    ret  z            ; stock $2458-$245A:  fe 14 c8
```

**KLM changes one byte:**

```asm
    cp   $14
    ret  nc           ; KLM  $244D-$244F:   fe 14 d0
```

`ret nc` returns at 20 *or above*, so an L or M start never transitions. The fix
is correct and complete.

**How this was got wrong.** The analysis searched for `cp $14`, found it
unchanged at KLM's relocated address, and concluded the cap had not been raised
— without checking the instruction after it. The measurement said to be
"verified empirically" measured our own build's behaviour, not KLM's.
Tolstoj: *"the latest implementation should not transition from L… I thought I
fixed it"*. He had.

**What to take from it:** a one-byte difference inverted the conclusion, and the
byte was one instruction past where the analysis stopped looking. Reading the
operand is not reading the instruction.

The Lab now makes the same change (`HOOK_LEVEL_CAP`), because it is better than
what we had: our own version compared against `MAX_LEVEL` and stopped only on
equality with 22, so L still climbed to M.

### 3.2b A second bug: hearts make K, L and M *slower*

**[VERIFIED EMPIRICALLY 2026-08-20]**

Hard mode ("hearts") is `min(level + 10, 20)`, and that ceiling of 20 was written when 20 was the
highest level in the game:

```asm
    ld   a, $0a
    add  e            ; level + 10
    cp   $15          ; >= 21 ?
    jr   c, .getIndexInDE
    ld   a, $14       ; clamp to 20
```

Once L (21) and M (22) exist, `level + 10` overflows the ceiling and the clamp pulls the speed
*down*:

| Level | Plain | With hearts | |
| --- | --- | --- | --- |
| 9 | 11 f/row | 4 f/row | hearts help, as intended |
| K (20) | 3 | 3 | no-op |
| **L (21)** | **2** | **3** | **hearts are slower** |
| **M (22)** | **1** | **3** | **hearts are three times slower** |

KLM's copy of this routine is byte-identical to stock apart from the table pointer — re-verified
2026-08-21, `3e 0a 83 fe 15 38 02 3e 14` in both — so **KLM has
this too**. Unlike the level-cap bug in §3.2 it is trivially reachable: arm hearts on the title
screen, pick M.

**Our fix is deliberately not in the formula.** Raising the ceiling would change how *normal* heart
games behave — a heart game saturates at level-20 speed from in-game level 10 onward, and players
rely on that. Instead the Lab simply does not offer hearts in the K-M bank, where they can never
help: at K they are a no-op and at L and M they only slow the game down. Hearts are cleared on
entering that bank and Select is ignored there. Zero bytes of the original formula change.

### 3.3 Implementation cost: the same feature, two ways

Adding levels L and M is one table extension. What it costs depends entirely on whether you are
editing a binary or a disassembly.

| | KLM | tetris-lab-gb |
| --- | --- | --- |
| Approach | Relocate the table to `$1AF1` to make room | Put a 23-entry table in reclaimed `$ff` padding, redirect the pointer |
| Bytes changed in the original banks | **20 870** | **54** |
| Regions changed | **80** | **6** |
| Bank 0 layout | Everything after the table shifts | Unchanged |
| Reviewable? | No — a 20 KB binary diff | Yes — every changed byte is declared and asserted |
| Level-up cap | Missed (§3.2) | Raised, one byte |

**386× smaller diff for identical behaviour.** The difference is not skill; it is that a disassembly
lets the linker do relocation. "Add two entries to a table" is two lines of source, and everything
downstream moves automatically. In a binary, the same edit forces a hand-maintained cascade through
two thirds of the ROM — which is precisely why *"I tried restructuring the code and ended up breaking
the whole project"* (§3.5.8 of `docs/community-research.md`) was the outcome, and why no hack has
ever been merged with another.

Our 54 bytes break down as: 23 for the table, 22 for the far-call trampoline (Milestone 0.5), 2 for
the table pointer, 1 for the level cap, 6 for cartridge header and checksums.

### 3.4 Structure

Relocating the table shifted everything after it, so KLM differs from stock in **20 870 bytes across
80 regions — 64 % of the ROM** — despite being, conceptually, a handful of edits. It is a whole-binary
rewrite with no source.

**This is the concrete form of the problem this project solves.** Tolstoj's *"I tried restructuring
the code and ended up breaking the whole project"* (§3.5.8) is the inevitable outcome of maintaining
a 20 KB binary diff by hand. In a disassembly, "extend the gravity table by two entries" is two
lines, and the linker relocates everything.

## 4. SPS — the seeded ROM

### 4.1 The mechanism

The stock piece randomiser reads the hardware divider register:

```asm
$2042  F0 04        ldh  a, [rDIV]
$2044  47           ld   b, a
```

The seeded ROM replaces those two bytes with five:

```asm
$202B  CD 32 05     call $0532          ; step the PRNG
$202E  F0 A3        ldh  a, [$FFA3]     ; read the result
$2030  47           ld   b, a
```

The `+3` bytes account exactly for the code shift measured either side of the patch site.
Everything downstream — the `×4` counting loop, the OR-rejection retry, the biased distribution — is
**untouched**. Only the entropy source changed.

The same substitution is applied to `PopulateGameScreenWithRandomBlocks` (the two `rDIV` reads at
`$1B6F`/`$1B83` that generate B-type starting garbage), so **B-type garbage is seeded too**.
`ShuffleHiddenPieces2Player` keeps its `rDIV` read.

### 4.2 The PRNG

A **16-bit LFSR**, state held in otherwise-unused HRAM at `$FFA2` (high) / `$FFA3` (low):

```asm
$0532  push af / push hl
       ld   a, [$FFA2] / ld h, a        ; hl = state
       ld   a, [$FFA3] / ld l, a
       ld a,h / rra / ld a,l / rra / xor h / ld h,a
       ld a,l / rra / ld a,h / rra / xor l / ld l,a / xor h / ld h,a
       ld   a, h / ld [$FFA2], a        ; store back
       ld   a, l / ld [$FFA3], a
       pop hl / pop af / ret
```

Transcribed and simulated: **maximal-length, period 65535** for any non-zero seed.

**It is not a textbook polynomial.** An exhaustive sweep of all 32 768 Galois masks and all 32 768
Fibonacci tap sets — both shift directions, either output byte, output taken before or after the
step — reproduces it **zero times**. The `rra`/`xor` chain above is a hand-rolled byte-wise
construction, not a shift register in standard form.

That matters for anyone trying to identify a *related* generator from its output alone: the
enumerable families do not contain even this one, so a null result against them says nothing about
whether a candidate is an LFSR. Recovering a widened version of this construction from recorded
pieces is program synthesis, not a parameter search. Ask the author instead.

> **`$0000` is a degenerate seed — period 1, always returns `0`.** The title screen displays
> `SEED 0000` as its default. This may be part of what nells meant by *"it's also not perfect SPS
> iirc"*. Worth raising with the community, and worth guarding against in our own implementation.

### 4.3 Seed entry and link sync

The title screen gains a **`SEED 0000`** field — a 16-bit seed as four hex digits, matching the LFSR
state width. The routine at `$0555` drives `rSB`/`rSC`, so the ROM **exchanges seeds over the link
cable**, which is what Muf meant by *"automatically synchronise SPS seeds"* (§3.5.3).

### 4.4 Recommendation: adopt this LFSR exactly

**Implement the identical LFSR with identical state semantics.** If we do, a given seed produces the
*same piece sequence* on our ROM as on theirs — so a player on the seeded ROM and a player on
TetrisGYM-GB can play the same seed against each other. For a feature whose entire purpose is
fairness between two players, **interoperability is the feature**. An objectively better PRNG that
produced different sequences would be worse.

This also supersedes the plan in `docs/architecture.md` §4.2 to seed by filling the existing
256-byte `wRandomness` table and forcing the `.predefined` branch. That approach was sound and
cheap, but it would produce **different sequences** from the ROM the community already uses, and it
inherits the 256-piece wrap problem. Hooking the entropy source is both simpler and compatible.
`docs/research.md` §8 #3 (the wrap question) is moot under this design.

## 5. The sprint / qualification ROMs

All four modify **`VBlankInterrupt` at `$0041`** — that is where the frame timer increments — and
`RST_00` at `$0001`. The 2025 CTEC ROM is much larger (29 533 B changed), consistent with Pascal's
description of a purpose-built, zero-configuration qualification ROM (§3.5.4).

Not yet decoded in detail. Before implementing our own timer we still need the exact start/stop
semantics (§7 A15) — Tolstoj's *"stops the timer one frame after the piece locks"* — because a timer
that disagrees by a frame makes results incomparable.

## 6. Cross-cutting observations

* **A shared base.** KLM and the seeded ROM contain several identical small edits — `$0049`
  (`LCDCInterrupt`), `$0076`, `$00C9`, `$019A-$01D9` (64 B in `VBlankInterruptHandler`), `$0298`,
  `$02A1`. They descend from a common ancestor hack. Notably `$0049` replaces the stubbed LCD STAT
  interrupt vector with a real handler.
* **No hack combines features.** KLM has levels but no SPS; the seeded ROM has SPS but *"only basic
  level starts"* (nells). They cannot be merged because each is a whole-binary rewrite against the
  same stock ROM. **In a disassembly they are simply two source files.** This is the single clearest
  argument for the project.
* **Everything is cramped into 32 KB.** No hack uses a mapper, which caps how far any of them can go.

## 7. What this changes

| Was | Now |
| --- | --- |
| M1 scoped to levels 0–20 (A–K) because L/M were unknown | **A–M is fully specified.** Extend the table to 23 entries; L=`$01`, M=`$00` |
| SPS design: fill `wRandomness`, force `.predefined` | **Replace the `rDIV` read with the community's exact LFSR**, for seed compatibility |
| 256-piece wrap an open question | Moot — we no longer use the table |
| v1.1 the community standard "on technical grounds" | Proven: all seven patches target CRC `46DF91AD` |

---

## SPS: reloading the LFSR is not enough

**Reported by Tolstoj, 2026-08-21; reproduced and fixed the same day.**

> *"for the SPS make sure everything resets on init, so the flood prevention
> (OR-logic) guarantees same sets"*

The piece generator draws again when the new piece's top six bits match the last
one's (`$205B`), and that test reads `hHiddenLoadedPiece` (`$FFAE`) — which
**nothing resets between games**. The original never had to care: `rDIV` is
random either way.

With a seed it matters. Left over from a previous game, the leftover value costs
an extra rejection on the very first draw and shifts the whole sequence by one:

```
same seed, fresh boot   [64, 72, 144, 64, 56, 136]
same seed, after a game [48, 64, 72, 144, 64, 56]
```

Fixed by zeroing it in `LabArmSeed`, and only when a seed is armed, so unseeded
play stays bit-identical to the original. `tests/test_sps.py` asserts a seeded
sequence is unchanged by a game played before it.

**Why our tests missed it:** they compared two runs that both started from a cold
boot, where the byte is zero in each. Any test that starts from a clean state
cannot see state that leaks between games.
