# 10. Seeds are Toni's 24-bit LFSR

**Status:** accepted, 2026-08-23 (supersedes the 16-bit LFSR shipped in v0.1–v0.3)

## Context

SPS is the community's oldest request, and its value is that two players can race the same
sequence. That only works if a seed means the same thing on both ROMs.

We shipped the community's 16-bit LFSR, transcribed from the seeded ROM in circulation. Tolstoj
asked for six-digit seeds; Toni was already building a 24-bit generator, and nobody used the
four-digit seeds, so there was nothing to preserve.

## Decision

Ship Toni's 24-bit LFSR exactly. Seeds are **six hex digits**, loaded raw as the state,
`$000000` meaning off.

We could have written our own — any maximal-length 24-bit LFSR is statistically equivalent, and the
game's own counting loop and re-roll dominate what a player actually sees. That is precisely why
matching his is free: there was nothing to gain and a community split to lose.

## The tap constant was recovered, not given

His file references `LFSR_MASK_LOW` and does not define it. `$87` was found by testing all 256
values against the four recorded piece sequences he sent: all 1023 written pieces match across four
seeds, and the next-best candidate matched 14. It is x^24 + x^7 + x^2 + x + 1, primitive, period
16 777 215 — confirmed by walking the whole cycle.

`tests/test_lfsr_vectors.py` keeps his sequences as the acceptance test, and asserts the mask
explicitly, so a future edit that changes it fails loudly rather than diverging silently.

## Consequences

* **Seeds from v0.3 and earlier do not carry over.** Intended, and stated in the release notes.
* **The routine fits bank 1 with three bytes to spare** — 39 of the 42 between the sound engine and
  the sound thunks. Two things made that possible: `rr` collapses his three hand-written shift
  blocks into three instructions, and `rlca / xor` pairs adjacent taps so the parity of `$87` costs
  seven bytes rather than twelve. Without both it needed a bank-2 thunk.
* **The three state bytes are stored high first**, matching his layout. That also lets a nibble
  index address its byte with a shift instead of a branch, which is what pays for six menu digits.
* **The seed row draws two columns left of every other row's value.** Six digits do not fit where
  four did — the menu starts at column 3, so the shared value column lands on 16 and the screen ends
  at 19.

## What this cost to find

One wrong inference, recorded because it wasted the most time: his dumps were measured to be *raw*
LFSR output rather than in-game pieces, on a repeat-rate statistic. They are in-game pieces. The
statistic assumed independent uniform draws, and consecutive LFSR low bytes share seven of eight
bits — the state shifts one place per step. That wrong conclusion invalidated an exhaustive search
which had `$87` inside its space all along: the search was fine, the oracle was wrong.

**Check what a statistic assumes about independence before trusting it against a generator whose
whole job is to be correlated.**
