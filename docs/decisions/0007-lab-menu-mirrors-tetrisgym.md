# 7. The Lab menu is TetrisGYM's list, on the screen the game already had

**Status:** accepted, 2026-08-21 (Milestone 2)

## Context

Trainers need somewhere to be chosen from. Until now there were two features and
both fitted beside the level grid (ADR 0003); a list of trainers does not.

TetrisGYM solves this with **one scrolling list**
(`src/gamemode/gametypemenu/menu.asm`): playable modes first, settings after,
each row carrying its own value edited in place. `TETRIS` is row 0 and `B-TYPE`
is row 6 of the same list — there is no A/B branch. Start is ignored on rows
past `MODE_GAME_QUANTITY`, which is how modes and settings are separated.

## Decision

**Mirror that list, on the A-TYPE/B-TYPE screen's own states** — `$08` paints
it, `$0E` runs it, the pair the original used. The Lab redraws the tilemap and
handles its own input; the original handlers never run. The copyright screen is
skipped at `$24`, so boot reaches the title in 1.3 s instead of 9.8 s, and the
menu is one press past it.

**The title screen keeps `$06`/`$07`, and 2 PLAYER is chosen there.**
`SerialFunc0_titleScreen` (`$0078`) assigns a multiplayer role only while
`hGameState` says `$07`, and forces every other state back to `$06`. Putting
the choice anywhere else means either moving the rendezvous or being yanked off
the screen the moment a cable is attached.

Rows: `TETRIS`, `B-TYPE`, `TRANSITION`, `SEED`, `MUSIC`. Up/Down move,
Left/Right edit the row's value, Start or A launches. `SEED` and `MUSIC` are
settings, so Start does nothing on them — the same split TetrisGYM draws.

**The seed lives here, not on the level select.** It is configuration, not part
of choosing a level, and TetrisGYM keeps it on the menu row too. The level
select is back to a level picker and nothing else.

**`SEED` borrows the D-pad.** Four digits need a cursor, so A opens the row and
A or Start closes it; while open, Left/Right pick a digit and Up/Down change it,
with the active one blinking. TetrisGYM leaves Up and Down free for its list
because it scrolls under a throttle; ours does not, so the row has to be
explicitly entered.

**ADR 0003 still stands.** It rejected a menu *for the level picker*, which
belongs on the level select. This is a different screen and a different job:
choosing the drill, not configuring it.

## Where the source of truth is

**NES TetrisGYM specifies how a trainer behaves. Game Boy evidence decides which
trainers exist.** Both halves matter, and `docs/community-research.md` has an
example of getting it wrong in each direction: the transition trainer was first
marked DROP because *"GB has no level-19/29 transition wall"* — NES-shaped
reasoning that binned the highest-value feature in the matrix — while a faithful
port would ship a killscreen trainer for a game whose speed caps at level 20.

About a third of TetrisGYM's list does not survive the crossing: no T-spin
scoring, no killscreen, one timing domain, no NES crash bug. Hard drop is out of
scope by decision (CLAUDE.md §12).

## The first trainer: TRANSITION

Chosen by community evidence — §6.2 ranks it third behind SPS and the level
select, both already done, and it is the one thing a practitioner named
unprompted as *"the most annoying thing"* in their routine.

**The level comes from the level select and nowhere else**, as it does for every
TetrisGYM trainer: its game type menu does one `inc gameMode` on Start, landing
on the level menu (`src/gamemode/gametypemenu/menu.asm`). Only Double Killscreen
skips it, because that mode sets level 29 itself.

**The row carries the trainer's own parameter: the score you start on, in
hundreds of thousands.** Set it to 5 and start on 18 and you begin at 500 000,
which is TetrisGYM's maxout trainer. `transitionModeSetup`
(`src/gamemodestate/initstate.asm`) writes the value into the high nibble of the
third BCD byte and presets the score from it; ours does the same into
`wScoreBCD + 2` up to 9, then overflows into the seventh digit: `A` is
1 000 000, `F` is 1 500 000. Writing `$A0` into a BCD byte the way theirs does
would put a letter in the score.

Their row has one more value, `G`, which turns the trainer off for Game Genie
`SXTOKL` compatibility — a code that changes the NES's first-transition formula.
The Game Boy levels up every ten lines from the start level and has no such
formula, so ours stops at `F`.

The line fill is theirs too: the counter goes to the last ten-line boundary
before the level advances. The Game Boy's transition is that boundary — the
original treats the start level as the number of tens to clear, so a level 9
start transitions at 100 lines and the drill begins at 90.

Topping out returns to the level select, which is also what TetrisGYM does
(`src/gamemodestate/handlegameover.asm` sets `gameMode` to `levelMenu`), and the
trainer stays selected so instant restart re-runs the drill.

## Two-player, and how it is tested

**`2 PLAYER` is the title screen's right-hand option**, where the game has
always put it. Link-cable head-to-head VS is CTWC-GB's *bracket format*
(`docs/community-research.md` §2), so dropping it was never an option. The
screen does what the original's did: a passive ping every frame, and the
master's announcement on confirm.

**Both are transcribed byte for byte**, not reimplemented — `tests/test_link.py`
asserts the original's `$0488` and `$04C5` sequences appear verbatim in the Lab's
banks.

**What can be tested, and what cannot.** PyBoy's serial is a stub (`set_SB`
hard-codes `$FF`, *"connecting is not implemented yet"*), so no exchange between
two units can be emulated. Everything the Lab itself does is still checkable, and
is checked: that it pings every frame with the same `SC` the stock title screen
does, that a role being assigned hands over to `$2A` with no keypress, that the
master path starts when a partner is already found, and that with nothing
attached the wait completes and the menu stays put.

What is left unverified is the physical byte exchange — which happens in
`SerialInterruptHandler`, original code the Lab does not touch. **Nobody has run
link play on this ROM on hardware.** That was equally true before this change.

## Consequences

* **A per-frame gameplay hook now exists** (`$00`, `HOOK_STATE_TABLE00`). The
  transition trainer needs it because the original's in-game init clears the
  line counter *after* any earlier hook could set it — verified in an emulator,
  not assumed. Trainers that act during play all land here rather than adding a
  hook each, which is what keeps the count from growing per feature.
* **The original A-TYPE/B-TYPE screen is gone**, and with it the combined music
  selector it shared. `MUSIC` is a menu row instead. The artwork stays in the
  ROM, unreferenced.
* **The menu repaints on entry, not per frame**, with the LCD off, as the
  original does for every screen change. No VBlank cost.
* **The menu loads its tileset through a bank-1 thunk.**
  `LoadAsciiAndMenuScreenGfx` is in bank 0 but reads `Gfx_Ascii` from bank 1, so
  it cannot be called while bank 2 is mapped, and bank-2 code must not switch
  banks itself (ADR 0001). Seven bytes in the linker's own empty gap at `$6430`
  solve it. Without this the level select rendered the *title* screen's tiles —
  the same layout, unreadable.
* **The title screen's init is ours**, and the clears in it are load-bearing.

  What made that hard to get right: **the falling piece collides against
  `wGameScreenBuffer`, and it is the title init that puts the walls and floor
  there** — two black columns and a black row at offset `$241`. Replacing the
  init without them leaves a piece falling past the bottom for ever, sprite
  never written, no game ever ending. It looks nothing like a drawing bug, and
  the buffer is not obviously a collision structure. The clears in that init are
  transcribed for the same reason: assume any of it is cosmetic at your peril.

  `tests/test_labmenu.py` asserts those three runs appear **byte for byte** in
  the Lab's banks, in order and adjacent — the same treatment the serial ping
  gets. Deleting the floor again fails that test by name, rather than by hanging
  a game somewhere unrelated.
* **The menu starts the music the `MUSIC` row is set to.** The screens it
  replaced each started their own — the title screen played `MUS_TITLE_SCREEN`,
  the A/B screen played the chosen type (`$1481`). The chosen type is the one to
  play here, because that row is where you audition it.
* **Settings persist; the original cleared them.** Passing through the title
  screen cleared `hATypeLevel`, `hBTypeLevel` and `hBTypeHigh` (`$04DB`). The
  menu does not: a trainer keeps the drill you set up, which is the same reason
  instant restart returns you to the level you *chose* rather than the one you
  reached (ADR 0005). Nothing depends on the clearing — `Reset` zeroes all of
  HRAM at `$028A`, on cold boot and soft reset alike, so none of it can start as
  garbage.
* **B on a level select returns to the menu.** It goes to `$08`, which is the
  menu's own init.
* **The line readout must be repainted by hand.** The original only redraws it
  on a line clear, so a drill would otherwise show `000` until the first one.
* **Every tilemap cell the Lab paints with the LCD on goes through
  `StoreAinHLwhenLCDFree`.** The hardware drops writes made while a line is being
  drawn, and the original's helpers do not guard against it —
  `DisplayBCDNum2CDigits` writes with a bare `ld [hl+], a` because it is only
  ever called with the LCD idle, so the Lab renders the line count itself rather
  than calling it.

  This cost three bugs that looked unrelated: a menu cursor that vanished at
  random, a line count that read `0`, `10` or `20` instead of `90`, and a music
  letter that never changed. Waiting for VBlank once and then painting is *not*
  enough — the window is ten lines and the last cells painted fall outside it,
  which is why the music letter, painted last, was the one that stayed stale.

  **PyBoy does not enforce VRAM blocking, so none of them failed a test.** Only
  hardware-accurate timing shows them. Treat any "it works in the tests but not
  on screen" report as this until proven otherwise.
