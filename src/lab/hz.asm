; --------------------------------------------------------------------------
; The tap rate
;
; How fast you are tapping, in Hz, in the box the score usually has. Nothing
; scores in OBSTACLE - no line ever clears - so the panel is free, and the number
; the drill is actually about is the one worth putting there.
;
; The formula is TetrisGYM's, which is HydrantDude's (src/modes/hz.asm):
;
;     hz = 60.098 * (taps - 1) / (frames - 1)
;
; taps counts fresh Left and Right presses; frames counts from the first tap of
; the window, so at the nth tap it already holds frames-1. A tap in the other
; direction, or one arriving more than sixteen frames after the last, starts a
; new window; so does the sixteenth tap. Those rules are theirs too - a number
; that means something different on the two ROMs would be worse than none.
;
; Computed on the tap, never in VBlank, and shown to two decimals like theirs.
; --------------------------------------------------------------------------

DEF HZ_DEBOUNCE  EQU $10        ; frames of quiet that end a window
DEF HZ_MAX_TAPS  EQU $10        ; and the tap that ends one
DEF HZ_SCALE     EQU 6010       ; 60.098 Hz x 100, which is TetrisGYM's $177A

; The SCORE box: row 1 is its label, row 3 its digits. The reading is five
; cells wide, so it sits in columns 15-19 and the label goes over it.
DEF HZ_LABEL_CELL EQU _SCRN0 + 1 * 32 + 14
DEF HZ_VALUE_CELL EQU _SCRN0 + 3 * 32 + 15
DEF TILE_POINT    EQU $24
DEF TILE_H        EQU $11
DEF TILE_Z        EQU $23


LabHzReset::
	xor  a
	ld   [wLabHzTaps], a
	ld   [wLabHzFrames], a
	ld   [wLabHzDir], a
	ld   [wLabHzValue], a
	ld   [wLabHzValue + 1], a
	ld   a, HZ_DEBOUNCE
	ld   [wLabHzDebounce], a
	ld   a, $ff                     ; nothing on screen matches: paint at once
	ld   [wLabHzDrawn], a
	ld   [wLabHzDrawn + 1], a
	ret


; The label, over the score's. Written once - the layout is drawn at the game
; init and nothing repaints row 1 afterwards.
LabHzLabel::
	ld   hl, HZ_LABEL_CELL
	ld   a, TILE_EMPTY
	call LabPutBothMaps
	inc  hl
	ld   a, TILE_EMPTY
	call LabPutBothMaps
	inc  hl
	ld   a, TILE_H
	call LabPutBothMaps
	inc  hl
	ld   a, TILE_Z
	call LabPutBothMaps
	inc  hl
	ld   a, TILE_EMPTY
	jp   LabPutBothMaps


LabHzTick::
; The frame counter runs only once a window is open. It saturates rather than
; wrapping: a window nobody is tapping in is already dead, and a wrapped count
; would read as a very fast one.
	ld   a, [wLabHzTaps]
	and  a
	jr   z, .notTapping
	ld   a, [wLabHzFrames]
	inc  a
	jr   z, .notTapping
	ld   [wLabHzFrames], a
.notTapping:

; The reading falls to zero when you stop, on the same sixteen frames that end
; the window. Leaving the last one up reads as the rate you are tapping at, and
; the rate you are tapping at is nothing.
	ld   a, [wLabHzDebounce]
	cp   HZ_DEBOUNCE
	jr   z, .debounced
	inc  a
	ld   [wLabHzDebounce], a
	cp   HZ_DEBOUNCE
	jr   nz, .debounced
	xor  a
	ld   [wLabHzValue], a
	ld   [wLabHzValue + 1], a
.debounced:

; A tap is Left or Right on its own. Both at once is a fumble, not a tap, and
; TetrisGYM does not count it either.
	ldh  a, [hButtonsPressed]
	and  PADF_LEFT | PADF_RIGHT
	jr   z, LabHzDraw
	cp   PADF_LEFT
	jr   z, .tap
	cp   PADF_RIGHT
	jr   nz, LabHzDraw

.tap:
	ld   b, a
	ld   a, [wLabHzDir]
	cp   b
	jr   nz, .fresh                 ; the other way: a new window
	ld   a, [wLabHzDebounce]
	cp   HZ_DEBOUNCE
	jr   nz, .within                ; tapped recently: the same window
.fresh:
	ld   a, b
	ld   [wLabHzDir], a
.restart:
	xor  a
	ld   [wLabHzTaps], a
	ld   [wLabHzFrames], a
.within:
	ld   hl, wLabHzTaps
	inc  [hl]
	ld   a, [hl]
	cp   HZ_MAX_TAPS
	jr   nc, .restart               ; the sixteenth tap opens the next window
	xor  a
	ld   [wLabHzDebounce], a

	ld   a, [wLabHzTaps]
	cp   2
	jr   c, LabHzDraw               ; one tap is not a rate
	call LabHzCompute
	; falls through


; Only when it changes: this runs every frame, and the box is ours alone, so
; there is nothing to repaint against.
LabHzDraw::
	ld   a, [wLabHzValue]
	ld   b, a
	ld   a, [wLabHzDrawn]
	cp   b
	jr   nz, .paint
	ld   a, [wLabHzValue + 1]
	ld   b, a
	ld   a, [wLabHzDrawn + 1]
	cp   b
	ret  z

.paint:
	ld   a, [wLabHzValue]
	ld   [wLabHzDrawn], a
	ld   a, [wLabHzValue + 1]
	ld   [wLabHzDrawn + 1], a

	ld   a, [wLabHzValue + 1]
	ld   h, a
	ld   a, [wLabHzValue]
	ld   l, a
	call LabDigits4

	ld   hl, HZ_VALUE_CELL
	ld   a, [wLabDigits]
	and  a
	jr   nz, .tens
	ld   a, TILE_EMPTY              ; nobody taps at 60 Hz, so blank the ten
.tens:
	call LabPutBothMaps
	inc  hl
	ld   a, [wLabDigits + 1]
	call LabPutBothMaps
	inc  hl
	ld   a, TILE_POINT
	call LabPutBothMaps
	inc  hl
	ld   a, [wLabDigits + 2]
	call LabPutBothMaps
	inc  hl
	ld   a, [wLabDigits + 3]
	jp   LabPutBothMaps


; hz x 100 = HZ_SCALE * (taps - 1) / frames.
;
; taps - 1 is at most fourteen, so the multiply is a loop of adds - smaller than
; any general routine and no less exact. The frame count cannot reach 256: the
; debounce ends a window after sixteen quiet frames and the sixteenth tap ends
; it too, so a live window spans at most fifteen gaps of fifteen frames. That
; is what lets the divide take an eight-bit divisor.
LabHzCompute::
	ld   a, [wLabHzTaps]
	dec  a
	ld   b, a
	xor  a
	ld   [wLabHzProd], a
	ld   [wLabHzProd + 1], a
	ld   [wLabHzProd + 2], a

.add:
	ld   a, [wLabHzProd]
	add  LOW(HZ_SCALE)
	ld   [wLabHzProd], a
	ld   a, [wLabHzProd + 1]
	adc  HIGH(HZ_SCALE)
	ld   [wLabHzProd + 1], a
	ld   a, [wLabHzProd + 2]
	adc  0
	ld   [wLabHzProd + 2], a
	dec  b
	jr   nz, .add

	ld   a, [wLabHzFrames]
	and  a
	ret  z
	ld   c, a

; Long division, twenty-four bits: the product shifts left out of the top into
; the remainder and the quotient shifts in at the bottom, so it ends where it
; started. The remainder is one bit wider than a byte for one instruction - the
; carry out of `rla` carries that bit, and a remainder that overflowed is
; always over the divisor.
	ld   b, 24
	xor  a

.divide:
	ld   hl, wLabHzProd
	sla  [hl]
	inc  hl
	rl   [hl]
	inc  hl
	rl   [hl]
	rla
	jr   c, .subtract
	cp   c
	jr   c, .nextBit

.subtract:
	sub  c
	ld   hl, wLabHzProd
	set  0, [hl]

.nextBit:
	dec  b
	jr   nz, .divide

; The quotient is at most 6010, so the top byte is spent.
	ld   a, [wLabHzProd]
	ld   [wLabHzValue], a
	ld   a, [wLabHzProd + 1]
	ld   [wLabHzValue + 1], a
	ret
