; Lab far-call trampoline.
;
; Lives in the original ROM's entry-point padding ($00DA-$00FF, 38 bytes of
; $FF). Must stay in bank 0, because the caller may be executing from any bank.
;
; Calling convention:
;     b  = target bank
;     hl = target address
;   FarCall preserves A (so a far routine can return a value in it) and
;   clobbers B and the flags. Nesting depth 1 only - hLabBank holds the bank to
;   restore, and a nested FarCall would overwrite it.
;
; The original game already writes 1 to $2000 during init (verified at $0252),
; which on MBC1 selects bank 1 - the correct default. See docs/research.md 3.6.
;
; hLabBank starts at zero, and the restore below used to write that back. On
; MBC1 a write of 0 selects bank 1, so it happened to be right; on MBC5 it
; selects bank 0 and maps it over $4000-$7FFF, where the sound engine, the
; ascii tiles and LabRandom live. Tolstoj's flash carts are MBC5. Writing 1
; instead is correct on both, and identical to what MBC1 was already doing.

FarCall::
	ldh  a, [hLabBank]
	push af                 ; stash the bank we came from
	ld   a, b
	ldh  [hLabBank], a
	ld   [$2000], a         ; MBC1 ROM bank select
	call .jumpHL
	ld   b, a               ; preserve the far routine's return value
	pop  af                 ; a = previous bank (flags clobbered)
	and  a
	jr   nz, .haveBank
	inc  a                  ; never select bank 0: see above

.haveBank:
	ldh  [hLabBank], a
	ld   [$2000], a
	ld   a, b
	ret

.jumpHL:
	jp   hl


; Lab state hook.
;
; The game-state jump table does `jp hl` to whichever handler it selects, so a
; redirected entry lands here. We hand control to Lab code in bank 2, which
; does its own work and returns - in HL - the address of the original handler
; to run. That keeps this stub at 9 bytes and lets Lab own the decision.
;
; Bank 2 code must never switch banks itself: it executes from $4000-$7FFF, so
; the instruction after the switch would be fetched from the new bank. All
; switching happens here in bank 0, which is always mapped.

LabStateHook::
	ld   b, BANK(LabDispatch)
	ld   hl, LabDispatch
	call FarCall
	jp   hl
