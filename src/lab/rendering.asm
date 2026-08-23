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
