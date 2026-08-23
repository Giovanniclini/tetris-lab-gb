; SPS - same piece sequence.
;
; The original draws pieces from the hardware divider register: `ldh a, [rDIV]`
; inside a retry loop, once per attempt. Everything downstream - the x4 counting
; loop, the bitwise-OR rejection test, the resulting bias - is left exactly as
; it was. Only the entropy source changes.
;
; The generator below is NOT ours. It is Toni's 24-bit LFSR, sent as source on
; 2026-08-22 (docs/existing-hacks.md section 4). His file omits the tap
; constant; $87 was recovered from the four recorded piece sequences he sent
; with it - all 1023 written pieces across four seeds, next-best candidate 14 -
; and verified maximal, period 16 777 215. Polynomial x^24 + x^7 + x^2 + x + 1.
;
; That it is his is the point: for a fairness mechanism, interoperability *is*
; the feature. A seed must deal the same pieces on our ROM as on his, so an
; objectively better generator producing different sequences would be worse.
; This replaces the community's 16-bit LFSR; nobody had four-digit seeds worth
; preserving.
;
; Lives in the 42 bytes of empty space between the sound engine and the sound
; thunks in bank 1, so it needs no room in bank 0 and shifts nothing. Bank 1 is
; mapped throughout gameplay, which is the only time this is called.

INCLUDE "include/hardware.inc"

SECTION "Lab Random", ROMX[$7FC6], BANK[1]

; Replaces `ldh a, [rDIV] / ld b, a` at each call site - three bytes for three,
; so nothing moves. Returns the value in B, as those two instructions did.
; Preserves HL, which the piece generator uses as its retry counter.
LabRandom::
	ldh  a, [hLabSpsEnabled]
	and  a
	jr   nz, .seeded

; SPS off: behave exactly like the original.
	ldh  a, [rDIV]
	ld   b, a
	ret

; Toni's step, with his three hand-written shift blocks folded into three `rr`
; instructions - rotate-right-through-carry is exactly a 24-bit shift with the
; feedback entering at the top. Only H has to survive the call: the generator
; keeps its retry count there, and writes D and E itself afterwards.
.seeded:
	push hl
	ld   hl, wLabRngLo
	ld   a, [hl]
	ld   b, a                       ; the low byte, and the value we return

; carry = parity of bits 0, 1, 2 and 7 - the taps of $87.
;
; `rlca` then `xor b` pairs every bit with the one below it, so bit 0 becomes
; b7^b0 and bit 2 becomes b1^b2. Those two together are exactly the four taps,
; so folding bit 2 onto bit 0 finishes it. Seven bytes rather than the twelve a
; mask-and-fold takes, which is what makes this fit bank 1 at all.
	rlca
	xor  b
	ld   d, a
	rrca
	rrca
	xor  d
	rrca                            ; and into the carry

	dec  hl
	ld   e, [hl]                    ; mid
	dec  hl
	ld   d, [hl]                    ; high

	rr   d                          ; the 24-bit shift, feedback entering first
	rr   e
	rr   b

	ld   [hl], d
	inc  hl
	ld   [hl], e
	inc  hl
	ld   [hl], b
	pop  hl
	ret


SECTION "Lab Bank 1 Gfx Thunk", ROMX[$7FF6], BANK[1]

LabLoadMenuGfx::
	call TurnOffLCD
	call LoadAsciiAndMenuScreenGfx
	ret


SECTION "Lab Bank 1 Thunk", ROMX[$6430], BANK[1]


; ---------------------------------------------------------------------------
; Score uncap
;
; The original stops the score at 999 999 by pinning all three BCD bytes to $99
; when the add carries out of the top one ($0178). That is the ceiling of the
; storage, not a rule: three BCD bytes hold six digits and the clamp exists to
; stop them wrapping to zero.
;
; The clamp is replaced by a jump here. By this point the add has already
; wrapped the three bytes to the low six digits, so all that is missing is the
; carry - one more BCD byte, giving digits 7 and 8.
;
; AddScoreValueDEontoBaseScoreHL is generic: it adds into whatever HL points at,
; from five different call sites. Only the live score gets a carry digit, so the
; pointer is checked first.
;
; In bank 1 because the clamp is reached during gameplay, when bank 2 is not
; mapped.
; ---------------------------------------------------------------------------

; A and the flags are not preserved: the clamp this replaces ended with $99 in A,
; so no caller can have relied on either.
LabScoreCarry::
	ld   a, h
	cp   HIGH(wScoreBCD + 2)
	jr   nz, .notTheLiveScore
	ld   a, l
	cp   LOW(wScoreBCD + 2)
	jr   nz, .notTheLiveScore

; Stop at 9, so the ceiling is 9 999 999. There is no room on screen for an
; eighth digit - column 11 is inside the playfield - so counting past 9 would
; only make the display lie, which is worse than a ceiling ten times the
; original's. Toni's build adds digits 7 and 8; when we take his format this
; comes back.
	ld   a, [wLabScoreMillions]
	cp   $09
	jr   z, .ceiling
	add  $01
	daa
	ld   [wLabScoreMillions], a

.notTheLiveScore:
	ret

; At the ceiling, pin every digit the way the original pinned its six. Simply
; refusing the carry is not enough: the add has already wrapped the low six, so
; the score would fall from 9 999 950 to 9 000 350.
.ceiling:
	ld   a, $99
	ld   [hl-], a
	ld   [hl-], a
	ld   [hl], a
	ret
