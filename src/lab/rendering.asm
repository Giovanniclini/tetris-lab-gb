; --------------------------------------------------------------------------
; Tilemap writes
;
; The Lab's two primitives for putting a tile on screen, and the one
; indicator drawn with them.
;
; VBlank is the scarcest resource on this machine and the original's handler
; is already near-full, so nothing here does arithmetic - callers arrive with
; the tile and the address already worked out.
; --------------------------------------------------------------------------

; A = tile, HL = destination. The hardware drops tilemap writes made while a
; line is being drawn, so every cell the menu paints goes through here.
; Preserves BC and DE, which StoreAinHLwhenLCDFree does not.
LabPutTile::
	push bc
	call StoreAinHLwhenLCDFree
	pop  bc
	ret


; Show whether hearts are armed, in the blank strip beside "LEVEL".
LabDrawHearts::
	ldh  a, [hIsHardMode]
	and  a
	ld   a, TILE_HEART
	jr   nz, .paint
	ld   a, TILE_FRAME

.paint:
	ld   b, a

.waitVBlank:
	ldh  a, [rLY]
	cp   SCRN_Y
	jr   c, .waitVBlank

	ld   a, b
	ld   [HEART_CELL], a
	ret


; ---------------------------------------------------------------------------
; Four decimal digits
;
; HL = a value under 10000, out into wLabDigits most significant first. The font
; puts 0-9 at $00-$09, so a digit is its own tile.
;
; Repeated subtraction rather than a divide: four digits is at most thirty-six
; adds, and `add hl, bc` with a negative BC is the test and the subtraction in
; one instruction - carry is set exactly when the result did not go below zero.
; DE keeps the value from before the add that did.
; ---------------------------------------------------------------------------

LabDigits4::
	ld   bc, -1000
	call .digit
	ld   [wLabDigits], a
	ld   bc, -100
	call .digit
	ld   [wLabDigits + 1], a
	ld   bc, -10
	call .digit
	ld   [wLabDigits + 2], a
	ld   a, l
	ld   [wLabDigits + 3], a
	ret

.digit:
	ld   a, -1
.count:
	inc  a
	ld   d, h
	ld   e, l
	add  hl, bc
	jr   c, .count
	ld   h, d
	ld   l, e
	ret


; ---------------------------------------------------------------------------
; The four digits on screen, at HL on both maps, leading zeros blanked the way
; the original's own number display blanks them - the units digit always shows,
; so zero reads as "0" rather than as nothing.
; ---------------------------------------------------------------------------

LabPutDigits4::
	ld   c, 0                       ; a digit has been drawn
	ld   de, wLabDigits
	ld   b, 4

.next:
	ld   a, [de]
	inc  de
	and  a
	jr   nz, .draw
	ld   a, c
	and  a
	jr   nz, .drawZero
	ld   a, b
	dec  a
	jr   z, .drawZero               ; the units digit always shows
	ld   a, TILE_EMPTY
	jr   .put

.drawZero:
	xor  a
.draw:
	ld   c, 1
.put:
	push bc
	push de
	call LabPutBothMaps
	pop  de
	pop  bc
	inc  hl
	dec  b
	jr   nz, .next
	ret


; ---------------------------------------------------------------------------
; The bright alphabet
;
; A tile row is two bytes - the low bitplane then the high one - so copying the
; font with the high plane zeroed leaves every glyph in the lighter shade
; instead of the darkest. LAB_FONT_TILES glyphs, from $00 to LAB_BRIGHT.
;
; VRAM, so the LCD must be off. Both callers are screen inits, which is the only
; time it is.
; ---------------------------------------------------------------------------

; Where the block lands, as a byte a test can read. A constant duplicated into
; the test is a constant that can be wrong in one place: the first version of
; the collision test carried its own copy and passed against the wrong range.
LabBrightBase::
	db LAB_BRIGHT


LabMakeBrightFont::
	ld   hl, _VRAM
	ld   de, _VRAM + LAB_BRIGHT * 16
	ld   bc, LAB_FONT_TILES * 8     ; rows, not tiles

.nextRow:
	ld   a, [hl+]
	ld   [de], a                    ; the plane that stays
	inc  de
	inc  hl
	xor  a
	ld   [de], a                    ; and the one that goes
	inc  de
	dec  bc
	ld   a, b
	or   c
	jr   nz, .nextRow
	ret
