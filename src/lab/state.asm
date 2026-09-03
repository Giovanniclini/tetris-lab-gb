; --------------------------------------------------------------------------
; Lab state - HRAM and WRAM
;
; Every byte the Lab owns, and the reasoning for where it sits. Kept apart
; from the code because the addresses are the constraint, not the routines:
; the original leaves two free bytes of HRAM and one large WRAM gap, and
; both are enumerated here.
; --------------------------------------------------------------------------

; hram.s declares a real SECTION, so it cannot be included twice. Its labels
; are exported and resolve at link time; these are the ones we use.
; Keep in sync with src/original/include/hram.s.

; ---------------------------------------------------------------------------
; HRAM
;
; The original leaves exactly two bytes of HRAM free ($FFFD-$FFFE); everything
; below $FFFD is in use. hLabBank must be in HRAM because the trampoline uses
; `ldh`, and because it is touched on every bank switch.
; ---------------------------------------------------------------------------

SECTION "Lab HRAM", HRAM[$FFFD]
hLabBank:: db            ; ROM bank currently selected by FarCall

; Read once per piece draw, so it earns one of the two free HRAM bytes.
hLabSpsEnabled:: db

; ---------------------------------------------------------------------------
; WRAM
;
; Claimed from the one large gap the original leaves: $D762-$DF6F, 2062 bytes
; between the high score tables and the audio variables. Verified unused - no
; code in the disassembly references an address in that range.
;
; The first 351 bytes are not free after all: the original's own high score
; indexing runs into them for levels above the grid. They are claimed below as
; the continuation of that table, which is what they should always have been.
;
; NOTE: $C400 is NOT free in v1.1 (wDarkSolidBlocksUnderRandomBlocks lives
; there). An earlier draft of docs/architecture.md said otherwise, based on a
; less complete disassembly's memory map.
;
; Lab code must never write outside this range.
; ---------------------------------------------------------------------------

; ---------------------------------------------------------------------------
; A-type high scores for levels A-M
;
; The original's table is ten slots - one per grid level - and its index
; arithmetic (wATypeHighScores + level * HISCORE_SIZEOF, at $179A) has no bound
; check. A game played at A-M therefore filed its score off the end of the
; table, into whatever happened to be there.
;
; So put the missing slots there. This section continues the original table
; exactly, which makes the original routine correct for levels 0-22 without
; changing a byte of it. tests/test_menu.py asserts the two are contiguous.
;
; $D762 = wATypeHighScores + HISCORE_SIZEOF * 10. Written as a literal because
; a SECTION address must be known at assembly time, not link time.
; ---------------------------------------------------------------------------

SECTION "Lab High Scores", WRAM0[$D762]
wLabATypeHighScoresExt::
	ds HISCORE_SIZEOF * (MAX_LEVEL + 1 - 10)


SECTION "Lab State", WRAM0[$D8C1]
wLabState::

; The Lab menu's own cursor: which entry of the scrolling list it is on, how
; far the list has scrolled, and the auto-repeat counter for Up/Down. wLabMode
; still holds the mode that entry selects, so everything downstream of the menu
; is unchanged by the list growing sections and settings rows.
wLabMenuRow::    db
wLabMenuScroll:: db
wLabMenuDas::    db
wLabMenuBright:: db        ; tile offset for the row being painted: the bright
                           ; block while the selected row is on its lit half

; Level picker, shown in a single cell to the right of the original 0-9 grid.
wLabFocus::        db        ; 0 grid, 1 level
wLabPickerLevel::  db        ; 0-22, shown as 0-9 then A-M
wLabBlinkTimer::   db        ; frame counter for the focus blink
wLabBlinkPhase::   db        ; current blink phase

; The original's init copies the whole layout back over the screen after our
; init runs, so anything we draw during init is erased. Repaint a frame later.
wLabRedrawPending:: db

; Set while an instant restart is in flight, so MainLoop's reset check knows to
; leave it alone. Without it there is no way to tell our restart apart from the
; level select starting a game, which reaches the same state.
wLabRestarting:: db

; SPS state. Twenty-four bits, high byte first, matching Toni's layout - his
; own code notes that mid and low must be consecutive addresses, and keeping
; that order lets a nibble index address its byte by a shift rather than a
; branch. $000000 is degenerate - period 1, always returns zero - so it is
; spent as the "off" value. See docs/existing-hacks.md section 4.2.
wLabRngHi::  db
wLabRngMid:: db
wLabRngLo::  db

; The seed as configured on the menu, copied into the LFSR at the start of every
; game. Kept separate because the LFSR state advances during play, and a restart
; must repeat the sequence rather than continue it.
wLabSeedHi::  db
wLabSeedMid:: db
wLabSeedLo::  db

; Lab menu. wLabMode is the row the cursor sits on, and survives into the game
; so trainers can ask which drill is running.
wLabMode::        db        ; MODE_TETRIS / MODE_BTYPE / MODE_TRANSITION
wLabDrillPending:: db       ; set at game init, consumed on the first game frame
wLabDrillScore::  db        ; TRANSITION's starting score, in hundreds of
                           ; thousands: 0-9 then A-F, so F is 1 500 000.
wLabSeedDigit::   db        ; 0-5 while editing the seed row, else SEED_IDLE
wLabCrunch::      db        ; CRUNCH's width, TetrisGYM's own value: every 4 is
                           ; a column off the left, every 1 off the right
wLabCrunchPending:: db     ; set at game init, consumed on the first game frame
wLabCrunchRowsToSend:: db  ; rows of the crunch columns still to reach the screen
wLabObstacle::        db        ; OBSTACLE's column, TetrisGYM's own value: 1-$0E is
                           ; the left wall that many rows tall, $11-$1E the right
wLabObstaclePending:: db       ; set at game init, consumed on the first game frame
wLabObstacleWasSettling:: db   ; last frame's hPieceFallingState, to catch the edge
                           ; back to NONE that means a new piece
wLabObstacleRowsToSend:: db    ; rows of the rebuilt board still to reach the screen

; Tap rate. See hz.asm - the window, the arithmetic scratch, and what is on
; screen so it is only repainted on change.
wLabHzTaps::     db
wLabHzFrames::   db
wLabHzDebounce:: db
wLabHzDir::      db
wLabHzValue::    dw        ; hz x 100, binary
wLabHzDrawn::    dw
wLabHzProd::     ds 3

; Scratch for LabDigits4, which OBSTACLE's bar count shares with the rate.
wLabDigits::     ds 4

; Bars that have landed since the drill started, and what is on screen.
wLabObstacleBars::      dw
wLabObstacleBarsDrawn:: dw

; The controller as the player actually held it, before LabSuppressPushdown
; edits it. Anything that wants to *show* the input - toni asked for an input
; display - must read this, not the HRAM the game reads.
wLabButtonsHeld::    db
wLabButtonsPressed:: db

; The level whose millions are currently on the high score panel. The original's
; own handler repaints that panel when the grid cursor moves and knows nothing
; about our two cells, so this is what tells us they need redrawing.
wLabHiScoreLevelDrawn:: db

; Digits 7 and 8 of the score, BCD. The original's three bytes hold the low six
; and wrap; this counts the carries. See LabScoreCarry in random.asm.
wLabScoreMillions::  db

; What the seventh-digit cell currently shows, so it is only repainted on change.
wLabScoreCarryDrawn:: db

; Whether the zero the layout draws at the start of a game has been moved into
; the cell the score now ends in. A flag rather than a look at what is on
; screen: this runs from the gameplay hook, not VBlank, and a VRAM read there
; returns $FF whenever the PPU happens to be using it.
wLabScoreZeroMoved:: db

; The seventh digit of each stored high score. The original's entries are three
; BCD bytes - six digits - so an uncapped score has nowhere to keep its
; millions, and worse, cannot be ranked against one that has them. Three per
; level, in the same order as the entries they belong to, shifted alongside
; them. See LabFileHighScore.
wLabHiScoreMillions:: ds (MAX_LEVEL + 1) * 3

	ds 908
wLabStateEnd::

; The TRANSITION row's top value, shown as F. TetrisGYM has one more, G, which
; turns its trainer off for Game Genie SXTOKL compatibility - a code that
; changes the NES's first-transition formula. The Game Boy has no such formula,
; so there is nothing here for it to mean.
DEF DRILL_SCORE_MAX EQU $0f
