; --------------------------------------------------------------------------
; Score display past a million
;
; The seventh digit. The original's three BCD bytes hold six and the clamp
; that used to pin them is now a carry handler (random.asm); this draws what
; that carry counts.
; --------------------------------------------------------------------------

LabDrawScoreCarry::
	ldh  a, [hGameType]
	cp   GAME_TYPE_A_TYPE
	ret  nz                         ; B-type has no score panel

	ld   a, [wLabMode]
	cp   MODE_QCKTAP
	ret  z                          ; that box is the tap rate there

	ld   a, [wLabScoreMillions]
	and  a
	jr   nz, .carried

; Back under a million: the original owns 14-19, so only our own column needs
; clearing.
	ld   a, [wLabScoreCarryDrawn]
	and  a
	jr   z, .checkInitialZero
	xor  a
	ld   [wLabScoreCarryDrawn], a
	ld   hl, SCORE_CELL_EIGHTH
	ld   a, TILE_BOX_EDGE
	call LabPutBothMaps
	ld   hl, SCORE_CELL_FIRST
	ld   a, TILE_EMPTY
	jp   LabPutBothMaps

; The zero showing at the start of a game is not drawn - it comes from the
; layout, which puts it where the score used to end, at column 18. Nothing
; redraws the score until it changes, so it would sit one cell left of every
; digit that follows it. Move it once, on the first frame of the game.
.checkInitialZero:
	ld   a, [wLabScoreZeroMoved]
	and  a
	ret  nz
	inc  a
	ld   [wLabScoreZeroMoved], a

	ld   hl, SCORE_CELL_FIRST + 5   ; column 18, where the layout left it
	ld   a, TILE_EMPTY
	call LabPutBothMaps
	inc  hl
	ld   a, TILE_0
	jp   LabPutBothMaps

; Past a million the original's draw is wrong, not just short: it blanks leading
; zeros, so 1 000 350 would read as "350". Draw all seven, zeros and all.
;
; A frame behind - this hook runs in front of the handler that redraws the score
; - so a change shows six digits for one frame before the seven appear.
.carried:
	ld   [wLabScoreCarryDrawn], a
	jr   LabDrawWholeScore


; All seven digits, zeros and all. The original only redraws the score when
; drop points land and the piece has finished falling ($01DB), so anything that
; sets the score outside that - a trainer presetting it - has to draw its own.
LabDrawWholeScore::
; The eighth digit sits on the box's left edge. A background tile brings its own
; light backing, so the box reads one cell wider rather than broken - and the
; edge goes back the moment the score drops under ten million.
	ld   a, [wLabScoreMillions]
	ld   hl, SCORE_CELL_EIGHTH
	swap a
	and  $0f
	jr   nz, .eighth
	ld   a, TILE_BOX_EDGE           ; under ten million the box keeps its edge

.eighth:
	call LabPutBothMaps
	inc  hl

; Zero in the seventh is a real digit once the eighth exists - 10 000 050 reads
; "10000050", not "1 000050" - so it blanks only when there are no millions.
	ld   a, [wLabScoreMillions]
	and  a
	ld   a, TILE_EMPTY              ; under a million there is no seventh digit
	jr   z, .seventh
	ld   a, [wLabScoreMillions]
	and  $0f

.seventh:
	call LabPutBothMaps
	inc  hl

	ld   de, wScoreBCD + 2          ; BCD, most significant byte last
	ld   c, 3

.nextByte:
	ld   a, [de]
	push af
	swap a
	and  $0f
	call LabPutBothMaps             ; high nibble
	inc  hl
	pop  af
	and  $0f
	call LabPutBothMaps             ; low nibble
	inc  hl
	dec  de
	dec  c
	jr   nz, .nextByte
	ret


; A = tile, HL = a cell in screen 0. Writes it to screen 1 as well, so the score
; is still right when the pause screen swaps the maps over. Leaves A and HL as
; it found them.
LabPutBothMaps::
	ld   b, a                       ; StoreAinHLwhenLCDFree clobbers A while it
	call LabPutTile                 ; waits, so the tile has to be kept in B -
	ld   a, h                       ; LabPutTile preserves BC
	add  SCREEN1_OFFSET
	ld   h, a
	ld   a, b
	call LabPutTile
	ld   a, h
	sub  SCREEN1_OFFSET
	ld   h, a
	ret
