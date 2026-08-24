# Architecture Decision Records

Short records of decisions that constrain future work. Add one whenever a
choice would otherwise have to be re-derived — or, worse, silently reversed.

| # | Decision |
| --- | --- |
| [1](0001-lab-code-lives-in-bank-2.md) | Lab code lives in bank 2 and can never switch banks itself |
| [2](0002-redirect-never-insert.md) | Hook by redirecting pointers, never by inserting bytes |
| [3](0003-level-select-extends-the-original-screen.md) | Level select extends the original screen rather than adding a menu |
| [4](0004-pyboy-for-behavioural-tests.md) | PyBoy drives behavioural tests; the build stays dependency-free |
| [5](0005-instant-restart.md) | Instant restart hooks three places, not one |
| [6](0006-high-scores-for-levels-a-to-m.md) | High scores for A–M continue the original's table |
| [7](0007-lab-menu-mirrors-tetrisgym.md) | The Lab menu is TetrisGYM's list, on the screen the game already had |
| [8](0008-retire-the-hook-count-budget.md) | The hook count is not the budget; the diff test is |
| [9](0009-entering-an-original-routine-partway.md) | Entering an original routine partway, when its entry point is a register contract |
| [10](0010-seeds-are-toni-24-bit.md) | Seeds are Toni's 24-bit LFSR, six hex digits |
| [11](0011-lab-code-is-modular.md) | Lab code is many small files, textually included into one section |
| [12](0012-lab-screens-are-drawn-not-stored.md) | Lab screens are drawn at runtime; TREP designs them and edits the original's |
