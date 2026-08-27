; --------------------------------------------------------------------------
; High scores
;
; Filing a finished game and drawing the table, including the seventh digit
; the original's three BCD bytes cannot hold. The comparison is ours; the
; insert, the name and the display stay the original's (ADR 0009).
; --------------------------------------------------------------------------

; Keep the TOP SCORE panel showing the level you are actually about to play.
;
; The original drives it from hATypeLevel, which the Lab keeps as the grid index
; while the level field or the seed has focus - so it kept showing the grid
; cursor's scores while you had M selected. A-M have their own slots (see "Lab
; High Scores" above), so every level shows real scores.
;
; This is DisplayATypeHighScoresForLevel ($1795) with one substitution: the
; level comes from the picker instead of hATypeLevel. Borrowing hATypeLevel
; instead would be shorter, but the routine below busy-waits on the LCD and so
; can outlast a frame - leaving the borrowed value visible to everything else
; that runs in between.
LabUpdateHighScores::
	call DisplayDottedLinesForHighScore

	call LabHiScoreLevel
	ld   [wLabHiScoreLevelDrawn], a
	call LabHiScoreSlot
	push hl                         ; the seventh digits
	push de                         ; the entries
	call SetNewHighScoreIfAchieved_SendNameAndScoreToRamBuffer
	pop  de
	pop  hl
	jp   LabDrawHiScoreMillions


; The original blanks leading zeros, so an entry past a million reads as its
; last digits alone - 1 000 544 as "544". Redraw those rows whole, all seven
; digits, starting in the first of the two dotted cells the original leaves
; between the name and the score.
;
; hl = the row's seventh digit, de = its entry's high byte.
;
; This writes to wGameScreenBuffer, not VRAM, so unlike the in-game score it
; needs no wait for the LCD - the original copies the buffer up in its own time.
; ---------------------------------------------------------------------------
; High scores past a million
;
; Entries are three BCD bytes - six digits - so an uncapped score has nowhere
; to keep its seventh digit, and worse, cannot be ranked against one that has
; one: 1 000 050 stored as 000050 loses to 999 999. The seventh digits live in
; wLabHiScoreMillions, one per entry, shifted alongside the entries they
; belong to.
;
; Only the comparison is ours. The original's compare falls into
; .currScoreHigherThanAHighScore with c holding the rank, and that entry point
; discards the de it pops - it reloads the slot address from HRAM on the very
; next instruction - so it can be entered from outside with any word on the
; stack. Everything past it stays the original's: the shift, the dotted name,
; the song, the display buffer.
; ---------------------------------------------------------------------------

LabFileHighScore::
; A drill is not a run. TRANSITION hands you its preset on the first frame, so
; filing it puts a score in the level's table that nobody played - and CRUNCH is
; a different game on a narrower board, whose scores are not the same quantity.
; Same reasoning as ADR 0005, where the instant restart abandons a half-typed
; name: when you are drilling you want another go, not a leaderboard entry.
;
; The score is zeroed on the way out, exactly as the did-not-place path does,
; so the original's own call a moment later has nothing to file either.
	ld   a, [wLabMode]
	cp   MODE_TETRIS
	jr   nz, .notARun

	ldh  a, [hATypeLevel]
	call LabHiScoreSlot
	ld   a, d
	ldh  [h1stHighScoreHighestByteForLevel], a
	ld   a, e
	ldh  [h1stHighScoreHighestByteForLevel+1], a

	push hl                         ; the seventh digits, wanted again on a place
	ld   c, 3                       ; the original's rank: 3 beats 1st, 1 beats 3rd

.nextEntry:
	call .beatsEntry
	and  a
	jr   nz, .placed
	inc  hl
	inc  de
	inc  de
	inc  de
	dec  c
	jr   nz, .nextEntry

; Did not place. Leave the original's own call nothing to disagree with.
	pop  hl

.notARun:
	xor  a
	ld   [wScoreBCD], a
	ld   [wScoreBCD + 1], a
	ld   [wScoreBCD + 2], a
	ld   [wLabScoreMillions], a
	ret

.placed:
	pop  hl                         ; the level's first seventh digit
	ld   a, 3
	sub  c                          ; the entry we displace, 0-2
	push bc
	ld   b, a

; Shift the ones below it down, from the bottom up, alongside the scores and
; names the original is about to shift.
	ld   a, 2
	sub  b
	jr   z, .storeMillions

	ld   c, a
	push hl
	inc  hl
	inc  hl                         ; the last, which is overwritten first

.shiftDown:
	dec  hl
	ld   a, [hl+]
	ld   [hl], a
	dec  hl
	dec  c
	jr   nz, .shiftDown
	pop  hl

.storeMillions:
	ld   c, b
	ld   b, 0
	add  hl, bc
	ld   a, [wLabScoreMillions]
	ld   [hl], a

	xor  a                          ; the original clears the score it just
	ld   [wLabScoreMillions], a     ; filed; the seventh digit goes with it

	pop  bc                         ; the rank again
	push de                         ; the entry point pops a word and drops it
	jp   SetNewHighScoreIfAchieved_SendNameAndScoreToRamBuffer.currScoreHigherThanAHighScore

; Returns a = 1 if the score just played beats the entry at de (its high byte)
; and hl (its seventh digit). Preserves both.
.beatsEntry:
	push hl
	push de
	push bc
	ld   a, [hl]
	ld   b, a
	ld   a, [wLabScoreMillions]
	cp   b
	jr   c, .lost
	jr   nz, .won

	ld   hl, wScoreBCD + 2
	ld   b, 3

.nextByte:
	ld   a, [de]
	sub  [hl]
	jr   c, .won                    ; the entry is the smaller
	jr   nz, .lost
	dec  l
	dec  de
	dec  b
	jr   nz, .nextByte
	                                ; every digit equal is not better

.lost:
	pop  bc
	pop  de
	pop  hl
	xor  a
	ret

.won:
	pop  bc
	pop  de
	pop  hl
	ld   a, 1
	ret


; The level whose high scores are on screen. The grid cursor is the level while
; it has focus; above the grid it is the picker, and hATypeLevel has been parked
; on the last grid cell to keep that cursor somewhere valid.
; Moving the grid cursor is the original's handler, and it repaints the panel
; without touching our two cells - so the digits of the level you were looking
; at stayed on screen over every level after it. Redraw them when the level on
; show changes, and only then: every cell waits for the LCD.
LabRefreshHiScoreMillions::
	call LabHiScoreLevel
	ld   b, a
	ld   a, [wLabHiScoreLevelDrawn]
	cp   b
	ret  z
	ld   a, b
	ld   [wLabHiScoreLevelDrawn], a
	call LabHiScoreSlot
	jp   LabDrawHiScoreMillions


LabHiScoreLevel::
	ld   a, [wLabFocus]
	and  a
	jr   nz, .fromPicker
	ldh  a, [hATypeLevel]
	ret

.fromPicker:
	ld   a, [wLabPickerLevel]
	ret


; Redraw only the seventh digits, leaving the rest of the buffer alone. The name
; entry screen shares these rows, and refilling them there would wipe the name
; being typed.
LabRedrawHiScoreMillions::
	call LabHiScoreLevel
	call LabHiScoreSlot
	jp   LabDrawHiScoreMillions


; a = a level. Returns de = its first score's high byte, exactly as $1798
; computes it, and hl = the first of its three seventh digits.
LabHiScoreSlot::
	push af
	ld   hl, wATypeHighScores + 2
	ld   bc, HISCORE_SIZEOF

.toSlot:
	and  a
	jr   z, .found
	dec  a
	add  hl, bc
	jr   .toSlot

.found:
	ld   d, h
	ld   e, l
	pop  af
	ld   hl, wLabHiScoreMillions
	ld   c, a
	ld   b, 0
	add  hl, bc
	add  hl, bc
	add  hl, bc
	ret


LabDrawHiScoreMillions::
	ld   bc, wGameScreenBuffer + $1a4 + 6
	ld   a, 3

.nextRow:
	push af                         ; rows left
	ld   a, [hl]
	and  a                          ; Z if this entry never passed a million
	push hl
	push de
	push bc
	push af                         ; the digit, and whether there is one

	call nz, .drawRow               ; the seven digits, into the buffer

	pop  af
	pop  hl                         ; the buffer cell
	push hl
	jr   nz, .rowToScreen

; No digits: blank both cells, which is what the stock ROM shows there - its
; dotted run has a gap in it, and tests/test_labmenu.py compares the whole
; screen against the real thing. hl is left where it was, because
; .cellsToScreen blits from it: advancing it here copies one cell past the pair
; and leaves the first digit on screen through every later level.
	ld   a, TILE_BLANK
	ld   [hl], a
	inc  hl
	ld   [hl], a
	dec  hl
	ld   c, 2
	jr   .toScreen

.rowToScreen:
	ld   c, 8

.toScreen:
	call .cellsToScreen

	pop  bc
	ld   a, c                       ; down one row of the buffer
	add  GB_TILE_WIDTH
	ld   c, a
	jr   nc, .noCarry
	inc  b

.noCarry:
	pop  de
	pop  hl
	inc  hl                         ; the next row's seventh digit
	inc  de                         ; and its entry
	inc  de
	inc  de
	pop  af
	dec  a
	jr   nz, .nextRow
	ret

; a = the entry's millions byte, de = its high byte, bc = where it goes.
;
; Two digits, not one: the byte is BCD and holds both. A zero in the eighth is
; a leading zero and stays blank - the original suppresses those, and an entry
; of 1 000 050 reading as "01 000 050" would be the only number on the screen
; padded that way.
.drawRow:
	push bc
	pop  hl
	ld   b, a
	swap a
	and  $0f
	jr   nz, .eighth
	ld   a, TILE_BLANK
.eighth:
	ld   [hl+], a
	ld   a, b
	and  $0f
	ld   [hl+], a
	ld   c, 3

.nextByte:
	ld   a, [de]
	push af
	swap a
	and  $0f
	ld   [hl+], a
	pop  af
	and  $0f
	ld   [hl+], a
	dec  de
	dec  c
	jr   nz, .nextByte
	ret

; hl = the first buffer cell, c = how many.
;
; The original sends the names and the scores up as two separate blits and
; never touches the cells between them, and the copy that would carry the rest
; has already run by the time we get here. So this row goes by hand. Writing
; only the buffer leaves it on screen exactly as the player reported it:
; 1 000 257 shown as 257.
.cellsToScreen:
	ld   a, [hl]
	push hl
	ld   de, _SCRN0 - wGameScreenBuffer
	add  hl, de
	call LabPutTile                 ; preserves bc, so c survives the loop
	pop  hl
	inc  hl
	dec  c
	jr   nz, .cellsToScreen
	ret



; ---------------------------------------------------------------------------
; The Lab menu
;
; TetrisGYM's game type menu is one scrolling list where the playable modes come
; first and the settings follow, each row carrying its own value edited in place
; (src/gamemode/gametypemenu/menu.asm). This is that list, on the screen the
; original used to offer A-TYPE and B-TYPE - which was already "what do you want
; to play", and is the only menu screen the game has. See docs/decisions/0007.
;
; Up/Down move, Left/Right change the value on the row, Start or A launches.
; MUSIC is a setting, not a mode, so Start does nothing on it - the same split
; TetrisGYM draws at MODE_GAME_QUANTITY.
; ---------------------------------------------------------------------------

DEF MODE_TETRIS     EQU 0
DEF MODE_BTYPE      EQU 1
DEF MODE_TRANSITION EQU 2
DEF MODE_CRUNCH     EQU 3
DEF MODE_LAUNCHABLE EQU 4           ; rows below this start a game
DEF MODE_SEED       EQU 4
DEF MODE_MUSIC      EQU 5
DEF MODE_COUNT      EQU 6

DEF MENU_ROW0       EQU _SCRN0 + 6 * 32 + 3   ; first entry
DEF MENU_STRIDE     EQU 2 * 32                ; a blank line between entries
DEF MENU_TEXT_COL   EQU 2                     ; label starts 2 cells in
DEF MENU_VALUE_COL  EQU 13                    ; the row's value, right of it

; Six hex digits will not fit where the other rows put their value: the menu
; starts at column 3, so MENU_VALUE_COL lands on column 16 and four digits
; already reach the right edge of the screen. The seed row alone starts two
; cells earlier. Its label ends at column 8, so nothing is in the way, and no
; other row moves.
DEF MENU_SEED_COL   EQU 11
DEF SEED_DIGITS     EQU 6
; The original's arrow, put where nothing else lives. Neither Lab screen's
; tileset reaches $FF with anything it draws, and every screen reloads its
; tileset on entry, so one tile here is ours for as long as we are on screen.
DEF MENU_CURSOR     EQU $ff
DEF SEED_IDLE       EQU $ff                   ; wLabSeedDigit when not editing

NEWCHARMAP labfont
	CHARMAP "0", $00
	CHARMAP "1", $01
	CHARMAP "2", $02
	CHARMAP "3", $03
	CHARMAP "4", $04
	CHARMAP "5", $05
	CHARMAP "6", $06
	CHARMAP "7", $07
	CHARMAP "8", $08
	CHARMAP "9", $09
	CHARMAP "A", $0a
	CHARMAP "B", $0b
	CHARMAP "C", $0c
	CHARMAP "D", $0d
	CHARMAP "E", $0e
	CHARMAP "F", $0f
	CHARMAP "G", $10
	CHARMAP "H", $11
	CHARMAP "I", $12
	CHARMAP "J", $13
	CHARMAP "K", $14
	CHARMAP "L", $15
	CHARMAP "M", $16
	CHARMAP "N", $17
	CHARMAP "O", $18
	CHARMAP "P", $19
	CHARMAP "Q", $1a
	CHARMAP "R", $1b
	CHARMAP "S", $1c
	CHARMAP "T", $1d
	CHARMAP "U", $1e
	CHARMAP "V", $1f
	CHARMAP "W", $20
	CHARMAP "X", $21
	CHARMAP "Y", $22
	CHARMAP "Z", $23
	CHARMAP ".", $24
	CHARMAP "-", $25
	CHARMAP " ", TILE_BLANK
SETCHARMAP main
