# 3. A level picker beside the grid, not a rebuilt grid

**Status:** accepted, 2026-08-20 (Milestone 1); navigation revised 2026-08-21.
Supersedes a rejected first attempt, kept below.

## Context

Levels 0-22 must be selectable. The original A-type screen offers 0-9 as a 5x2
grid of custom digit tiles (`$90-$99`) with a sprite cursor positioned from
`ATypeLevelsCoords`.

## Decision

**Leave the original grid completely alone** - same tiles, same cursor, same
movement - and add fields in the blank strip to its right. Columns 15-18, rows
4-11 are uniform background inside the border, and four columns is exactly a
16-bit seed in hex.

```
        cols 15-18
   row  6      .  L  .  .      level, A-M
   row  9      S  E  E  D
   row 10      A  C  E  1      seed, four hex digits
```

Focus moves in a chain: **grid -> level -> the four seed digits**. **Left and
Right walk the chain; Up and Down change the value under the cursor.**

* **Right on cell 9** gives the picker focus. The original ignores that press
  (`cp $09 / jr z`), so nothing has to be suppressed to reach it.
* **Left** leaves the level field for grid cell 9, from any level.
* **Select** toggles hearts, with a heart drawn beside `LEVEL`. The original
  never tests Select on this screen.
* **The picker offers `A`-`M` and nothing else.** The grid already offers `0`-`9`,
  and a level in both fields is one you can select in two places, with the
  cursor in one of them saying something different from the other. `Left`
  remains the way out of the field, from any level.
* The picker cell's tile is simply the level number: the font puts `0-9` at
  `$00-$09` and `A-M` at `$0A-$16`, so `tile == level` throughout.

Modelled on NES TetrisGYM, which does the same thing - the grid stays, a picker
appears beside it.

## The rejected first attempt, and why

The first design gave the grid three *banks* - `0-9`, `A-J`, `K-M` - cycled with
Down on the bottom row, repainting all ten cells. It passed thirteen tests and
was unusable in practice.

It failed because it fought the original screen in four places at once:

* The grid cursor is a **sprite that draws the character for the level** (spec
  index `$20 + level` picks a one-tile sprite), and the ROM has those specs
  **only for digits 0-9**. On a letter bank it drew a digit over a letter.
* Clamping the cursor without moving the sprite left it visibly parked on an
  empty cell.
* The original handler runs after ours and sees the same `hButtonsPressed`, so
  consumed presses had to be cleared or it moved the cursor again underneath us.
* Repainting ten cells every bank change fought the original's own repaint.

**The lesson is not "that was hard".** The tests passed because they asserted
what the implementation did, not what a player experiences. A design that needs
four separate fixes to coexist with the code around it is the wrong design; the
picker needs none of them.

## Consequences and gotchas that still apply

* **We run before *and* after the original handler.** The pre-pass reads input;
  the post-pass corrects the sprite. A post-pass is unavoidable because the
  original positions and copies the cursor sprite on its own terms.
* **Hiding a sprite means pushing it to OAM.** The original flashes the cursor
  by XOR-ing its hidden bit *and then copying the specs into OAM*. Setting the
  bit in the post-pass is too late on its own - the copy already happened - so
  the post-pass calls `Copy2SpriteSpecsToShadowOam` as well. Without that the
  cursor blinks on screen beside the picker.
* **Consume the inputs you act on**, with `res` on `hButtonsPressed`, or the
  original acts on them too.
* **Fold the picker level into `hATypeLevel` only when leaving the screen.**
  While the screen is up `hATypeLevel` stays a grid index so the original's
  cursor code works untouched.
* **Repaint one frame late.** The original's init copies the whole layout over
  the screen *after* our init runs, so a pending flag defers the paint.
* **Left/Right navigate, Up/Down edit - in every field.** *Revised 2026-08-21,
  reversing the original entry here.* The first version had Left/Right change
  the level and Down enter the seed, so the same two buttons meant "change the
  value" on one field and "move to the next field" on the next. Worse, Left had
  to do both: step down a level, and at 0 leave the field. Now `0` is just a
  level, and the way out is the same press everywhere.
* **A seed of `$0000` means "no seed"** - SPS off, pieces from `rDIV`, which is
  genuinely random. That spends the degenerate all-zero LFSR state as the "off"
  value rather than leaving it as a trap, and means there is nothing to
  randomise: clearing the seed *is* randomising.
* **No charmap is active in `src/lab/`**, so string literals assemble as ASCII.
  Letters written to the tilemap must be explicit tile indices.
* **The TOP SCORE panel follows the picked level.** It is driven by
  `hATypeLevel`, which the Lab keeps as the grid index, so it used to keep
  showing the grid cursor's scores while you had M selected. The table has ten
  slots, one per grid level; A-M have no storage, so those show the dotted
  placeholder the original already uses for empty entries.
* **Do not repaint the score panel on the deferred repaint.** The original's own
  init already paints it, and doing it again there cost `hATypeLevel` its value
  and silently reset heart speeds to level 0. Caught by a regression test that
  existed for exactly that reason.
* **Hearts are cleared above level 20.** Hard mode is `min(level + 10, 20)`, a
  ceiling written when 20 was the highest level; above it the clamp works
  *downward* and makes the game slower. Changing the formula would alter normal
  heart games, so the option is withheld instead. See
  `docs/existing-hacks.md` 3.2b.
