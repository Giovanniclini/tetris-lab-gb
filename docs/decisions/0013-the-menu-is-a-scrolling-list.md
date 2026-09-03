# 13. The menu is a scrolling list, drawn from Tolstoj's layout

**Status:** accepted, 2026-09-03. Extends [ADR 7](0007-lab-menu-mirrors-tetrisgym.md),
which stands: the menu is still TetrisGYM's list on the screen the game already
had, and 2 PLAYER is still chosen on the title screen.

## Context

The menu was six rows of a single screen, and every trainer added one. Single
spacing bought room for about twelve, which is a reprieve rather than a design.

Tolstoj sent a proof of concept on 2026-09-02: one list taller than the screen,
grouped under `STANDARD` / `COMPETITION` / `TRAINING` headers, scrolling under
the cursor. Layout drawn in TREP, 20 columns by 32 rows — exactly the height of
the background map — with room for four more entries and space to grow.

## Decision

**Adopt his design and his layout; write our own implementation.** The
generated source he sent with it is not ours to carry: he calls it ugly himself,
and it targets a memory map where the demo/multiplayer piece buffer has been
removed. Ours has not — `wDemoOrMultiplayerPieces` is what link play deals from,
and `docs/research.md` §3.5 calls it the project's biggest single opportunity.

**It stays on `$08`/`$0E`, not the title screen.** His POC replaces `$06`/`$07`
and has no 2 PLAYER anywhere. `SerialFunc0_titleScreen` (`$0078`) assigns a link
role only while `hGameState` is `$07`, so the title screen keeps the artwork,
`1 PLAYER` / `2 PLAYER`, and the version.

## Consequences and gotchas that still apply

* **VBlank zeroed the scroll register.** The handler cleared `rSCX` and `rSCY`
  at the end of every frame, so the background could not scroll at all: the menu
  wrote `rSCY` and the next VBlank threw it away, leaving the cursor correctly
  pinned to the anchor row over a picture that never moved. Deviation #23 points
  that one write at `hUnusedFFA4` — one byte, the operand alone, so `A` is still
  zero for the `inc a` that follows. Tolstoj's POC patches the same instruction.
  **The scroll is ours to clear on the way out**, because nothing clears it now.
* **Replacing `$08` took the tileset loader with it.**
  `GameState08_GameMusicTypeInit` (`$1452`) was the **only** place in the ROM
  that loaded the shared tileset; every screen after it inherited, and no level
  select or game init fetches one. The Lab menu replaced that screen and loads
  Tolstoj's artwork instead — 44 tiles of it above the font — so each screen
  downstream fetches its own now, inside the LCD-off window its init already
  opens. That is why `$12` is hooked: the Lab draws nothing on B-type's level
  select and is there only for the load.

  **Doing it on the way out of the menu instead does not work**, and the way it
  fails is worth keeping. It means opening a second LCD-off window, and the LCD
  has to come back up at the end of it or the next init hangs (below) — so one
  frame is displayed with the menu's map under the next screen's tiles. Blanking
  the map first hides that, and hiding it is all it does: a blank screen is
  still a screen nobody asked for. The test asserts the menu is *on screen* for
  every lit frame until it goes dark, not that those frames are empty.
* **Turning the LCD off is not free at a screen boundary.** Loading a tileset
  turns it off, and the init that follows opens with `TurnOffLCD`, which spins
  on `rLY == $91` — a VBlank an already dark LCD will never send.

  Turning it back on before handing over is *not* the answer, and this took
  three goes to see: it puts a lit frame between the tileset swap and the
  redraw, with the old map under the new tiles. Both level select inits are
  entered **past their own `call TurnOffLCD`** instead (`LAB_SKIP_TURN_OFF_LCD`,
  three bytes, the ADR 9 technique with no register contract to check), so the
  Lab's window and the original's are one window. `tests/test_expansion.py` pins
  what is at those two entry points; byte-exactness pins where they are.

  **Everything the next screen needs undone happens in that same dark window**,
  the scroll included. Clearing `rSCY` on the way out of the menu instead snaps
  the list to its top while it is still lit — invisible from a row near the top,
  which is why it survived until someone launched `OBSTACLE`.

  **The lesson is about the test, not the code.** Four passes at this, and each
  fix moved the bad frame somewhere the test was not looking: out of the state
  it watched, out of the frames it sampled, then into a row it never selected.
  It watches from the press frame itself to the destination now, over a row deep
  enough to have scrolled, and asserts the map, the tiles and the scroll all
  agree rather than that the frames are blank.
* **The version is drawn, not drawn in.** Tolstoj's first layouts had it baked,
  which is right on the day the file is cut and stale from the next release. It
  is written at init now, right-aligned against the header box's edge, the same
  rule the title screen uses — so a release needs no new layout from him.
* **The cursor is a sprite, and the drawn ones come out.** Tolstoj draws a
  cursor into his layouts — on the title screen the artwork's own arrow *is* the
  cursor. Here the list scrolls under the cursor, so a cell in the map scrolls
  with the list and cannot be one. Every entry's cursor column is blanked at
  init, not just the row he drew, so a re-cut layout cannot bring it back. **His
  `X` is already an OAM coordinate**; adding the usual 8 puts the arrow on the
  first letter of the label.
* **The light alphabet is shared.** It is made by `LabMakeBrightFont` and used
  by both the menu and the level select, whose unfocused picker is drawn in it -
  still readable, not the field you are changing, which is what the grid says
  with its own flashing cursor. It is VRAM, so each screen makes it in its own
  LCD-off window.

  **It goes at `$C6`, and the range was found by asking rather than by
  eye.** `$A0` looked free from the menu (`$9B`), the level select (`$99`) and
  the game (`$7D`) - and the game over screen underlines GAME and OVER with
  `$AD`, so those two words grew a row of faint `D`s. Reported by Giovanni.
  `tests/test_labmenu.py` now walks the title, both level selects, the game and
  the game over screen and checks nothing is drawn inside the block. The block's
  address is a byte in the ROM (`LabBrightBase`) that the test reads: the first
  version carried its own copy of the offset and passed against the wrong range
  while the ROM's had moved.
* **Bright text is the dark text with one bitplane cleared.** A tile row is two
  bytes, low plane then high, so copying the font with the high plane zeroed
  gives the same glyphs one shade lighter — a blinking value costs no artwork.
  **Only glyphs may be shifted into it:** the block is a copy of the font and
  stops where the font does, and `MUSIC` pads `OFF` out to six cells with
  blanks, each of which blinked into a different piece of the artwork.
* **The menu opens where it was left.** `wLabMenuRow` survives in WRAM and the
  scroll is derived from it, so coming back from a level select finds the row
  you launched from and the view you left. The loop is "set it up, try it, come
  back and change it", and a twelve-row list that always opens at the top makes
  its own length the price of that. A cold boot zeroes the row, which is the
  first entry.
* **A row shows more than it edits.** `OBSTACLE` carries a height and a wall,
  and Left and Right change only the height — the wall follows, because past the
  tallest left column is the shortest right one, which is TetrisGYM's own value
  order. Only the number blinks: the wall is not what the buttons are changing,
  and flashing it says otherwise.

  It is drawn even at height zero, where there is no column and no side. A row
  whose only mark is a nought reads as broken rather than as "nothing set", and
  Tolstoj's layout draws `0 L` for that reason.

  **A two-field editor was tried first and taken out again.** `SEED`'s shape -
  `A` to open, Left and Right to choose a field - left the row inert until you
  guessed the key, and cost a byte of state for a wall the value cannot hold at
  height zero. Showing two things and editing one is the simpler contract.
* **Row order is not mode order.** Settings sit above the modes and headers sit
  between them, so `wLabMode` is what the selected row *selects*, and the row
  itself is `wLabMenuRow`. Nothing downstream of the menu changed. Tests reach a
  mode with `Tetris.to_mode`, which navigates by what `wLabMode` reads — a press
  count is not a row any more, and the layout is Tolstoj's to change.
* **Values are painted for every row, every frame.** That is what puts a value
  back to black when the cursor leaves it: there is nothing to restore, the next
  frame simply paints it dark.
* **The paint loop dispatches on `C`.** A painter that needs `C` for itself has
  to save it — the seed painter left it holding six, which is `MODE_MUSIC`, and
  the music painter then ran on the seed's row and drew `B-TYPE` over the digits.
