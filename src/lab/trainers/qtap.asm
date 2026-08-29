; --------------------------------------------------------------------------
; QCKTAP
;
; A single column against one wall and nothing else, rebuilt for every piece,
; with an I-piece dealt every time. The drill is one skill: get the bar past
; the column and into the well before it lands - which is a tap, not a DAS
; charge, once the column is tall enough. TetrisGYM's mode of the same name
; (src/modes/qtap.asm), including its value, so a number means the same shape
; on both ROMs:
;
;   0        no column, bars on a flat floor
;   1-$10    left wall, that many rows tall
;   $11-$20  right wall, value - $10 rows tall
;
; The value is one tile on the menu, as every other row's is, and the labfont
; runs 0-9 then A-Z - so $20 shows as W, exactly as it does on TetrisGYM.
; --------------------------------------------------------------------------

DEF QTAP_MAX        EQU $20
DEF QTAP_RIGHT      EQU $11      ; the first value that means the right wall
DEF QTAP_LEFT_COL   EQU 1        ; playfield columns, as TetrisGYM picks them
DEF QTAP_RIGHT_COL  EQU 8
DEF QTAP_BOTTOM_ROW EQU GAME_SCREEN_ROWS - 1

; The I piece, in the original's own numbering: SpriteSpec_08 is the four-tile
; horizontal run ($8a $8b $8b $8f), and $08-$0b are its four rotations. The
; generator only ever produces multiples of 4, so this is a value it could have
; produced itself.
DEF QTAP_PIECE_I    EQU $08


; The playfield cleared, then the column. Buffer only - plain WRAM, no waiting
; on the LCD - so this is cheap enough to do whole rather than work out which
; cells the last piece dirtied. The screen catches up through the queue below.
;
; Columns 2-11 of the buffer, which is the playfield; columns 1 and $c are the
; walls the piece collides against and are not ours to clear.
LabQtapBuild::
	ld   hl, wGameScreenBuffer + 2
	ld   c, GAME_SCREEN_ROWS
.nextRow:
	push hl
	ld   b, GAME_SQUARE_WIDTH
	ld   a, TILE_EMPTY
.clearRow:
	ld   [hl+], a
	dec  b
	jr   nz, .clearRow
	pop  hl
	ld   de, GB_TILE_WIDTH
	add  hl, de
	dec  c
	jr   nz, .nextRow

; the column, from the floor up
	ld   a, [wLabQtap]
	and  a
	ret  z
	ld   c, a
	ld   e, QTAP_LEFT_COL + 2       ; playfield column -> buffer column
	sub  QTAP_RIGHT
	jr   c, .haveColumn             ; below $11: left wall, height is the value
	inc  a                          ; $11 is one row, not zero
	ld   c, a
	ld   e, QTAP_RIGHT_COL + 2

.haveColumn:
	ld   d, 0
	ld   hl, wGameScreenBuffer + QTAP_BOTTOM_ROW * GB_TILE_WIDTH
	add  hl, de
	ld   de, -GB_TILE_WIDTH
	ld   a, TILE_SOLID_BLOCK
.nextBlock:
	ld   [hl], a
	add  hl, de
	dec  c
	jr   nz, .nextBlock
	ret


; --------------------------------------------------------------------------
; Every gameplay frame
; --------------------------------------------------------------------------

; Rebuilt per piece, which is what makes this a drill rather than a board:
; TetrisGYM calls advanceGameTap from practiseEachPiece, once per piece, and
; clears the playfield each time - so a botched tap is wiped rather than stacked
; on.
;
; The signal is hPieceFallingState falling back to NONE. It leaves NONE when a
; piece touches down and walks HIT_BOTTOM -> CHECK_COMPLETED_ROWS ->
; ALL_ROWS_PROCESSED before returning, so the edge back to zero is exactly one
; per piece - and it says nothing about which piece, which is the point.
LabQtapApply::
	ld   a, [wLabMode]
	cp   MODE_QCKTAP
	ret  nz

	call LabHzTick
	call LabQtapNoDropPoints

; Every piece an I, the way TetrisGYM sends MODE_TAP to pickTetriminoLongbar.
; Not a hook: the generator ($2041) plays the piece it left in hHiddenLoadedPiece
; last time and hides a fresh random one there, so overwriting that byte before
; it runs decides the next piece without touching a byte of it. Its retry loop
; still compares its own random value, so the rejection bias, the LFSR and the
; three attempts all behave exactly as they do everywhere else.
	ld   a, QTAP_PIECE_I
	ldh  [hHiddenLoadedPiece], a

	ldh  a, [hPieceFallingState]
	ld   b, a
	ld   a, [wLabQtapWasSettling]
	ld   c, a
	ld   a, b
	ld   [wLabQtapWasSettling], a

	ld   a, [wLabQtapPending]
	and  a
	jr   nz, .firstFrame

	ld   a, b
	and  a
	jp   nz, LabQtapSendRows        ; still settling
	ld   a, c
	and  a
	jp   z, LabQtapSendRows         ; was already falling: the same piece
	jr   .landed

; The first frame of the game. The in-game init dealt the piece already on
; screen and the one in the preview, both before this ran, so those two are the
; only ones the line above cannot reach.
.firstFrame:
	xor  a
	ld   [wLabQtapPending], a
	ld   a, QTAP_PIECE_I
	ld   [wSpriteSpecs + SPR_SPEC_SpecIdx], a
	ld   [wSpriteSpecs + SPR_SPEC_SIZEOF + SPR_SPEC_SpecIdx], a

; The preview box is OAM, written once per piece by the generator - not rebuilt
; from the spec each frame the way the falling piece is. So changing the spec
; underneath it leaves the last sprite there, and after an instant restart the
; box showed a piece the game was never going to deal. Reported by Giovanni,
; who found that hiding and unhiding the box with Select cleared it - that is
; this same call, from the original's own handler.
	call Copy2ndSpriteSpecToSprite8

; The score box becomes the tap rate. Nothing scores in this drill - no line
; ever clears, and the drop points are suppressed with the push (gameplay.asm)
; - so the panel is free and the number the drill is about goes in it.
	call LabHzReset
	call LabHzLabel

; And the LINES box counts bars, which is the length of the drill. Nothing
; completes a line here either, so that panel is free the same way.
	xor  a
	ld   [wLabQtapBars], a
	ld   [wLabQtapBars + 1], a
	ld   a, $ff
	ld   [wLabQtapBarsDrawn], a     ; nothing on screen matches: paint at once
	call LabQtapDrawBars
	jr   .rebuild

; A bar has landed. Counted here rather than at the spawn so the number is
; bars *down*, which is what you have to show for the time spent.
.landed:
	ld   hl, wLabQtapBars
	inc  [hl]
	jr   nz, .rebuild
	inc  hl
	inc  [hl]

.rebuild:
	call LabQtapBuild
	ld   a, GAME_SCREEN_ROWS
	ld   [wLabQtapRowsToSend], a
	call LabQtapDrawBars
	; falls through


; The buffer is the game's collision map; this is the same board on the screen.
;
; Not by setting hRowsShiftingDownState: that is the row-shift state machine,
; and borrowing it freezes the piece and looks to the game like a completed line
; clear. CRUNCH found that the hard way - see the note there. So the rows go up
; on our own counter with a per-frame budget, which is what CLAUDE.md 11 asks
; Lab rendering to do. Three rows a frame puts the board on screen in six.
DEF QTAP_ROWS_PER_FRAME EQU 3

LabQtapSendRows::
	ld   a, [wLabQtapRowsToSend]
	and  a
	ret  z

	ld   c, QTAP_ROWS_PER_FRAME
.nextRow:
	ld   a, [wLabQtapRowsToSend]
	and  a
	ret  z
	dec  a
	ld   [wLabQtapRowsToSend], a

; row a of the playfield, in both the buffer and screen 0
	ld   h, 0
	ld   l, a
	add  hl, hl
	add  hl, hl
	add  hl, hl
	add  hl, hl
	add  hl, hl                     ; * GB_TILE_WIDTH
	push hl
	ld   de, wGameScreenBuffer + 2
	add  hl, de
	ld   d, h
	ld   e, l
	pop  hl
	ld   bc, _SCRN0 + 2
	add  hl, bc

	ld   b, GAME_SQUARE_WIDTH
.nextCell:
	ld   a, [de]
	inc  de
	call LabPutTile                 ; preserves bc and de
	inc  hl
	dec  b
	jr   nz, .nextCell

	dec  c
	jr   nz, .nextRow
	ret


; Set at the game init and consumed on the first gameplay frame: that init
; clears the playfield, so building it any earlier achieves nothing.
LabQtapArm::
	ld   a, [wLabMode]
	cp   MODE_QCKTAP
	ret  nz
	ld   a, 1
	ld   [wLabQtapPending], a
	xor  a
	ld   [wLabQtapWasSettling], a
	ld   [wLabQtapRowsToSend], a
	ret


; --------------------------------------------------------------------------
; The panels
; --------------------------------------------------------------------------

; Drop points, suppressed - the push itself is not. Holding Down is a legitimate
; way to end an attempt you have already lost, but the point it earns changes
; the score, and a score change repaints the SCORE box straight over the rate.
;
; No hook: the points come from a count of the frames Down was held ($20E3),
; and the routine skips the whole add when that count is zero. Clearing it each
; frame is the same thing the original does itself once it has paid out.
; Movement is driven by hTimer2 and the gravity reload, not by this byte, so the
; piece still drops.
LabQtapNoDropPoints::
	xor  a
	ldh  [hNumTimesHoldingDownEvery3Frames], a

; And the request to redraw the score that goes with them. The payout is set on
; the frame the piece hits bottom and the redraw waits for the rows to finish
; processing ($01DB), so there is at least one of our frames in between to
; withdraw it in.
	ld   [wATypeJustAddedDropsToScore], a
	ret


; Bars down, where the line count goes: row 10, column 14, four digits, which
; is where and how the original draws its own ($23E9). Only on change - nothing
; else writes there once no line can ever complete.
DEF QTAP_BARS_CELL EQU _SCRN0 + 10 * 32 + 14

LabQtapDrawBars::
	ld   a, [wLabQtapBars]
	ld   b, a
	ld   a, [wLabQtapBarsDrawn]
	cp   b
	jr   nz, .paint
	ld   a, [wLabQtapBars + 1]
	ld   b, a
	ld   a, [wLabQtapBarsDrawn + 1]
	cp   b
	ret  z

.paint:
	ld   a, [wLabQtapBars]
	ld   [wLabQtapBarsDrawn], a
	ld   a, [wLabQtapBars + 1]
	ld   [wLabQtapBarsDrawn + 1], a

	ld   a, [wLabQtapBars + 1]
	ld   h, a
	ld   a, [wLabQtapBars]
	ld   l, a
	call LabDigits4
	ld   hl, QTAP_BARS_CELL
	jp   LabPutDigits4
