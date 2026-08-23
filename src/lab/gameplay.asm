; --------------------------------------------------------------------------
; Gameplay corrections
;
; Changes to how the game plays, as opposed to what it shows. Each one is a
; thing the original does that a trainer must not teach.
; --------------------------------------------------------------------------

; ---------------------------------------------------------------------------
; No pushdown at L and M
;
; Holding Down moves the piece every three frames whatever the level ($2092).
; That is a speed-up everywhere the original can reach - gravity is 4 frames or
; slower up to level 19, and exactly 3 at level 20 - but L and M fall in 2 and 1.
; There, handing the piece to the pushdown timer makes it *slower*: it hitches
; rather than accelerates. Measured, tapping Down at M: gaps of 4 frames
; appearing in a 1-frame fall.
;
; Tolstoj: "for the pushdown, make sure L and M do not change their gravity".
;
; He skips the acceleration with a conditional jump. We cannot - that needs
; seven bytes inserted mid-routine and bank 0 has none - so the press is hidden
; instead, from the per-frame hook, which runs before the original reads it.
;
; The drop points go with it. One point per row pushed ($2126) is a reward for
; pushing, and at L and M there is no push, so there is nothing to reward.
;
; Gated on the gravity reload rather than the level: that is the real condition,
; and hATypeLinesThresholdToPassForNextLevel still holds an A-type value during
; a B-type game.
; ---------------------------------------------------------------------------

LabSuppressPushdown::
; Keep the real thing first, every frame, whether or not it gets edited. What
; the game reads is a lie from here on, and something will eventually want the
; truth - toni has already asked for an input display, which at L and M would
; otherwise show Down as unpressed while the player leans on it.
	ldh  a, [hButtonsHeld]
	ld   [wLabButtonsHeld], a
	ldh  a, [hButtonsPressed]
	ld   [wLabButtonsPressed], a

	ldh  a, [hNumFramesUntilPiecesMoveDown]
	cp   2                          ; stored as frames-1, so < 2 means under 3
	ret  nc

	ldh  a, [hButtonsHeld]
	res  PADB_DOWN, a
	ldh  [hButtonsHeld], a

	ldh  a, [hButtonsPressed]
	res  PADB_DOWN, a
	ldh  [hButtonsPressed], a
	ret



; ---------------------------------------------------------------------------
; The seventh score digit
;
; The SCORE panel is six cells at row 3, columns 13-18, and column 12 is the
; box's left edge - there is no seventh cell, which is why Tolstoj's ROMs put
; this digit in a sprite.
;
; A sprite does not work here: its colour 0 is transparent, so a dark digit on
; the panel's dark surround is invisible. A background tile carries its own
; light backing, so writing column 12 makes the box look one cell wider and the
; digit reads normally. Restored to the edge tile when the score is under a
; million.
;
; Written through LabPutTile, so it waits for the LCD like everything else.
; ---------------------------------------------------------------------------

; The original's six digits are drawn at columns 14-19 of *both* maps - screen 0
; for play, screen 1 for the pause screen - after deviation #20 moved them one
; cell right into the spare column. That leaves column 13 for the seventh digit,
; and the number stays put when it passes a million instead of shifting.
DEF SCORE_CELL_FIRST EQU _SCRN0 + $6d       ; row 3, column 13 - ours alone
DEF SCREEN1_OFFSET   EQU 4                  ; $9800 -> $9C00, in the high byte
