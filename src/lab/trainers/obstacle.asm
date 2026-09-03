; --------------------------------------------------------------------------
; OBSTACLE
;
; A single column against one wall and nothing else, rebuilt for every piece,
; with an I-piece dealt every time. The drill is one skill: get the bar past
; the column and into the well before it lands - which past level 19 is a tap
; rather than a DAS charge. TetrisGYM's mode (src/modes/qtap.asm), including
; its value, so a number means the same shape on both ROMs:
;
;   0          no column, bars on a flat floor
;   1-$0E      left wall, that many rows tall
;   $11-$1E    right wall, value - $10 rows tall
;
; TetrisGYM calls this QCKTAP. It is not that here: Game Boy DAS autorepeats
; every 9 frames, which is 6.68 Hz, so the skill this drills is getting past
; the column rather than out-tapping the hardware. Tolstoj, 2026-08-30:
; "quicktaps aren't really a thing in GB Tetris".
;
; The value is one tile on the menu, as every other row's is, and the labfont
; runs 0-9 then A-Z - so $1E shows as U.
;
; Fourteen rows, not TetrisGYM's sixteen, and that is the same rule rather than
; a different one. A standing bar is four rows tall, so it can only cross the
; column if the column's top is at row 4 or below; their sixteen on a 20-row
; field leaves exactly those four rows, and ours is 18 rows. At fifteen the bar
; stops two columns short of the well and the drill cannot be completed at all -
; measured, and reported by Tolstoj. The four values that would ask for it
; ($0F, $10, $1F, $20) are not offered.
; --------------------------------------------------------------------------

DEF OBSTACLE_HEIGHT_MAX EQU 14       ; four rows of headroom for a standing bar
DEF OBSTACLE_RIGHT      EQU $11      ; the first value that means the right wall
DEF OBSTACLE_MAX        EQU OBSTACLE_RIGHT + OBSTACLE_HEIGHT_MAX - 1
DEF OBSTACLE_LEFT_COL   EQU 1        ; playfield columns, as TetrisGYM picks them
DEF OBSTACLE_RIGHT_COL  EQU 8
DEF OBSTACLE_BOTTOM_ROW EQU GAME_SCREEN_ROWS - 1

; The I piece, in the original's own numbering: SpriteSpec_08 is the four-tile
; horizontal run ($8a $8b $8b $8f), and $08-$0b are its four rotations. The
; generator only ever produces multiples of 4, so this is a value it could have
; produced itself.
DEF OBSTACLE_PIECE_I    EQU $08

; The two things the value encodes, for the menu row that edits them.
DEF OBSTACLE_HEIGHT     EQU 0
DEF OBSTACLE_SIDE       EQU 1
DEF OBSTACLE_FIELDS     EQU 2


; a = the height the value stands for, 0 to OBSTACLE_HEIGHT_MAX.
LabObstacleHeight::
	ld   a, [wLabObstacle]
	cp   OBSTACLE_RIGHT
	ret  c                          ; the left wall: the value is the height
	sub  OBSTACLE_RIGHT - 1
	ret


; Carry when the column stands against the left wall.
LabObstacleOnLeft::
	ld   a, [wLabObstacle]
	cp   OBSTACLE_RIGHT
	ret


; b = a height, c = nonzero for the right wall. Stores the value they mean.
; A height of zero is no column at all, so it has no side to be on.
LabObstacleStore::
	ld   a, b
	and  a
	jr   z, .store
	ld   a, c
	and  a
	ld   a, b
	jr   z, .store
	add  OBSTACLE_RIGHT - 1

.store:
	ld   [wLabObstacle], a
	ret


; The playfield cleared, then the column. Buffer only - plain WRAM, no waiting
; on the LCD - so this is cheap enough to do whole rather than work out which
; cells the last piece dirtied. The screen catches up through the queue below.
;
; Columns 2-11 of the buffer, which is the playfield; columns 1 and $c are the
; walls the piece collides against and are not ours to clear.
LabObstacleBuild::
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
	ld   a, [wLabObstacle]
	and  a
	ret  z
	ld   c, a
	ld   e, OBSTACLE_LEFT_COL + 2       ; playfield column -> buffer column
	sub  OBSTACLE_RIGHT
	jr   c, .haveColumn             ; below $11: left wall, height is the value
	inc  a                          ; $11 is one row, not zero
	ld   c, a
	ld   e, OBSTACLE_RIGHT_COL + 2

.haveColumn:
	ld   d, 0
	ld   hl, wGameScreenBuffer + OBSTACLE_BOTTOM_ROW * GB_TILE_WIDTH
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
LabObstacleApply::
	ld   a, [wLabMode]
	cp   MODE_OBSTACLE
	ret  nz

	call LabHzTick
	call LabObstacleNoDropPoints

; Every piece an I, the way TetrisGYM sends MODE_TAP to pickTetriminoLongbar.
; Not a hook: the generator ($2041) plays the piece it left in hHiddenLoadedPiece
; last time and hides a fresh random one there, so overwriting that byte before
; it runs decides the next piece without touching a byte of it. Its retry loop
; still compares its own random value, so the rejection bias, the LFSR and the
; three attempts all behave exactly as they do everywhere else.
	ld   a, OBSTACLE_PIECE_I
	ldh  [hHiddenLoadedPiece], a

	ldh  a, [hPieceFallingState]
	ld   b, a
	ld   a, [wLabObstacleWasSettling]
	ld   c, a
	ld   a, b
	ld   [wLabObstacleWasSettling], a

	ld   a, [wLabObstaclePending]
	and  a
	jr   nz, .firstFrame

	ld   a, b
	and  a
	jp   nz, LabObstacleSendRows        ; still settling
	ld   a, c
	and  a
	jp   z, LabObstacleSendRows         ; was already falling: the same piece
	jr   .landed

; The first frame of the game. The in-game init dealt the piece already on
; screen and the one in the preview, both before this ran, so those two are the
; only ones the line above cannot reach.
.firstFrame:
	xor  a
	ld   [wLabObstaclePending], a
	ld   a, OBSTACLE_PIECE_I
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
	ld   [wLabObstacleBars], a
	ld   [wLabObstacleBars + 1], a
	ld   a, $ff
	ld   [wLabObstacleBarsDrawn], a     ; nothing on screen matches: paint at once
	call LabObstacleDrawBars
	jr   .rebuild

; A bar has landed. Counted here rather than at the spawn so the number is
; bars *down*, which is what you have to show for the time spent.
.landed:
	ld   hl, wLabObstacleBars
	inc  [hl]
	jr   nz, .rebuild
	inc  hl
	inc  [hl]

.rebuild:
	call LabObstacleBuild
	ld   a, GAME_SCREEN_ROWS
	ld   [wLabObstacleRowsToSend], a
	call LabObstacleDrawBars
	; falls through


; The buffer is the game's collision map; this is the same board on the screen.
;
; Not by setting hRowsShiftingDownState: that is the row-shift state machine,
; and borrowing it freezes the piece and looks to the game like a completed line
; clear. CRUNCH found that the hard way - see the note there. So the rows go up
; on our own counter with a per-frame budget, which is what CLAUDE.md 11 asks
; Lab rendering to do. Three rows a frame puts the board on screen in six.
DEF OBSTACLE_ROWS_PER_FRAME EQU 3

LabObstacleSendRows::
	ld   a, [wLabObstacleRowsToSend]
	and  a
	ret  z

	ld   c, OBSTACLE_ROWS_PER_FRAME
.nextRow:
	ld   a, [wLabObstacleRowsToSend]
	and  a
	ret  z
	dec  a
	ld   [wLabObstacleRowsToSend], a

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
LabObstacleArm::
	ld   a, [wLabMode]
	cp   MODE_OBSTACLE
	ret  nz
	ld   a, 1
	ld   [wLabObstaclePending], a
	xor  a
	ld   [wLabObstacleWasSettling], a
	ld   [wLabObstacleRowsToSend], a
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
LabObstacleNoDropPoints::
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
DEF OBSTACLE_BARS_CELL EQU _SCRN0 + 10 * 32 + 14

LabObstacleDrawBars::
	ld   a, [wLabObstacleBars]
	ld   b, a
	ld   a, [wLabObstacleBarsDrawn]
	cp   b
	jr   nz, .paint
	ld   a, [wLabObstacleBars + 1]
	ld   b, a
	ld   a, [wLabObstacleBarsDrawn + 1]
	cp   b
	ret  z

.paint:
	ld   a, [wLabObstacleBars]
	ld   [wLabObstacleBarsDrawn], a
	ld   a, [wLabObstacleBars + 1]
	ld   [wLabObstacleBarsDrawn + 1], a

	ld   a, [wLabObstacleBars + 1]
	ld   h, a
	ld   a, [wLabObstacleBars]
	ld   l, a
	call LabDigits4
	ld   hl, OBSTACLE_BARS_CELL
	jp   LabPutDigits4
