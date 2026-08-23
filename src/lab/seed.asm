; --------------------------------------------------------------------------
; The seed
;
; The six hex digits of the SPS seed: reading and editing one nibble at a
; time for the menu row, and copying the result into the LFSR at the start
; of every game.
;
; The generator itself is in random.asm - it has to live in bank 1, where the
; piece code can reach it.
; --------------------------------------------------------------------------

; Add B (1 or -1) to the nibble the focus is on, wrapping 0-F.
; C = digit index 0-3, leftmost first.
LabAdjustSeedNibble::
	call LabReadSeedNibble
	add  b
	and  $0f
	ld   d, a                       ; d = new nibble

; rebuild the byte the digit lives in
	call LabSeedNibbleByte
	ld   a, c
	and  1                          ; 0 = upper nibble, 1 = lower
	jr   nz, .lowerNibble

	ld   a, [hl]
	and  $0f
	swap d
	or   d
	ld   [hl], a
	ret

.lowerNibble:
	ld   a, [hl]
	and  $f0
	or   d
	ld   [hl], a
	ret


; Nibble C (0-5, leftmost first) of the seed, returned in A.
LabReadSeedNibble::
	call LabSeedNibbleByte
	ld   a, [hl]
	bit  0, c
	jr   nz, .lower
	swap a

.lower:
	and  $0f
	ret


; HL = the byte nibble C lives in. The three seed bytes are stored high first,
; so the byte is simply C/2 along - which is why they are in that order.
LabSeedNibbleByte::
	ld   a, c
	srl  a
	add  LOW(wLabSeedHi)
	ld   l, a
	ld   h, HIGH(wLabSeedHi)
	ret


; ---------------------------------------------------------------------------
; SPS seed
; ---------------------------------------------------------------------------

; Copy the configured seed into the LFSR and arm SPS, or disarm it.
;
; A seed of $0000 means "off": pieces come from rDIV, exactly as the original
; does, which is genuinely random. That also means the degenerate all-zero LFSR
; state can never be reached - it is spent as the "no seed" value instead of
; being a trap the way it is in the community's ROM (docs/existing-hacks.md 4.2).
LabArmSeed::
	ld   a, [wLabSeedHi]
	ld   [wLabRngHi], a
	ld   b, a
	ld   a, [wLabSeedMid]
	ld   [wLabRngMid], a
	or   b
	ld   b, a
	ld   a, [wLabSeedLo]
	ld   [wLabRngLo], a
	or   b                          ; seed zero?
	ldh  [hLabSpsEnabled], a        ; non-zero arms it, zero disarms it
	ret  z

; Reloading the LFSR is not enough on its own. The generator draws again when
; the new piece's top six bits match the last one's ($205B), and that test reads
; hHiddenLoadedPiece - which nothing resets between games. The original never
; had to care, because rDIV is random either way; with a seed it means the same
; seed deals a different sequence depending on what you played before it. Left
; over from one game, it costs an extra draw on the first piece and shifts the
; whole sequence by one.
;
; Reported by Tolstoj, 2026-08-21, and reproduced before fixing.
; Only when SPS is armed: unseeded play stays bit-identical to the original.
	xor  a
	ldh  [hHiddenLoadedPiece], a
	ret
