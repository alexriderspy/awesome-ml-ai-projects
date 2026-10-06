# Real CLI runs

Model: `deepseek-flash` via `https://api.deepseek.com`. Output copied as printed. Times are wall-clock per turn (including retries).

## LLM vs LLM: same model, two personas

```bash
PYTHONPATH=src python -m ttt_battle --x llm --o llm --persona-x aggressive --persona-o cautious
```

```
X = deepseek-flash (aggressive)   O = deepseek-flash (cautious)

1. X (deepseek-flash (aggressive)) -> 5   1.47s
   reasoning: Opening move; taking the center maximizes attacking options and fork potential.
    1 | 2 | 3
   ---+---+---
    4 | X | 6
   ---+---+---
    7 | 8 | 9

2. O (deepseek-flash (cautious)) -> 1   1.14s
   reasoning: X controls the center, so I take a corner to avoid losing and build toward a draw or win.
    O | 2 | 3
   ---+---+---
    4 | X | 6
   ---+---+---
    7 | 8 | 9

3. X (deepseek-flash (aggressive)) -> 3   101.43s
   reasoning: No immediate win or block exists. Play 3 to create a diagonal threat at 7 and force O to respond.
    O | 2 | X
   ---+---+---
    4 | X | 6
   ---+---+---
    7 | 8 | 9

4. O (deepseek-flash (cautious)) -> 7   2.23s
   reasoning: X threatens to win by playing 7 on the diagonal 3-5-7, so I must block at 7.
    O | 2 | X
   ---+---+---
    4 | X | 6
   ---+---+---
    O | 8 | 9

5. X (deepseek-flash (aggressive)) -> 4   2.15s
   reasoning: Opponent threatens to win next with O at 4 completing column 1 (1-4-7), so I must block at 4. I have no immediate winning move.
    O | 2 | X
   ---+---+---
    X | X | 6
   ---+---+---
    O | 8 | 9

6. O (deepseek-flash (cautious)) -> 6   2.98s
   reasoning: X threatens to win at 6 by completing the middle row, so I must block there. I have no winning move available now.
    O | 2 | X
   ---+---+---
    X | X | O
   ---+---+---
    O | 8 | 9

7. X (deepseek-flash (aggressive)) -> 8   33.78s
   reasoning: No immediate win or O threat; play 8 to create a column-2 threat, forcing O to block at 2.
    O | 2 | X
   ---+---+---
    X | X | O
   ---+---+---
    O | X | 9

8. O (deepseek-flash (cautious)) -> 2   4.01s
   reasoning: X threatens to win by playing cell 2 in the middle column, so I must block there.
    O | O | X
   ---+---+---
    X | X | O
   ---+---+---
    O | X | 9

9. X (deepseek-flash (aggressive)) -> 9   2.21s
   reasoning: Only cell 9 is empty, so I must play it; it does not create an immediate win or block a threat.
    O | O | X
   ---+---+---
    X | X | O
   ---+---+---
    O | X | X

RESULT: draw
```

## Minimax (X) vs LLM (O)

```bash
PYTHONPATH=src python -m ttt_battle --x minimax --o llm --seed 3
```

```
X = minimax   O = deepseek-flash

1. X (minimax) -> 4   0.05s
   reasoning: search: best moves [1, 2, 3, 4, 5, 6, 7, 8, 9], value 0 (draw with perfect play)
    1 | 2 | 3
   ---+---+---
    X | 5 | 6
   ---+---+---
    7 | 8 | 9

2. O (deepseek-flash) -> 5   3.06s
   reasoning: No immediate win or block is available; taking the center is the strongest opening response.
    1 | 2 | 3
   ---+---+---
    X | O | 6
   ---+---+---
    7 | 8 | 9

3. X (minimax) -> 8   0.0s
   reasoning: search: best moves [1, 2, 3, 7, 8, 9], value 0 (draw with perfect play)
    1 | 2 | 3
   ---+---+---
    X | O | 6
   ---+---+---
    7 | X | 9

4. O (deepseek-flash) -> 7   43.27s
   reasoning: No immediate win for O, but X threatens a fork by playing 7 (creating threats at 1 and 9). Playing 7 blocks that and also creates an immediate threat at 3.
    1 | 2 | 3
   ---+---+---
    X | O | 6
   ---+---+---
    O | X | 9

5. X (minimax) -> 3   0.02s
   reasoning: search: best moves [3], value 0 (draw with perfect play)
    1 | 2 | X
   ---+---+---
    X | O | 6
   ---+---+---
    O | X | 9

6. O (deepseek-flash) -> 9   31.48s
   reasoning: No immediate win or block is available. Playing 9 creates a diagonal threat at 1, forcing X to respond.
    1 | 2 | X
   ---+---+---
    X | O | 6
   ---+---+---
    O | X | O

7. X (minimax) -> 1   0.0s
   reasoning: search: best moves [1], value 0 (draw with perfect play)
    X | 2 | X
   ---+---+---
    X | O | 6
   ---+---+---
    O | X | O

8. O (deepseek-flash) -> 2   2.71s
   reasoning: X threatens to win by playing cell 2, completing the top row, so O must block at 2.
    X | O | X
   ---+---+---
    X | O | 6
   ---+---+---
    O | X | O

9. X (minimax) -> 6   0.0s
   reasoning: search: best moves [6], value 0 (draw with perfect play)
    X | O | X
   ---+---+---
    X | O | X
   ---+---+---
    O | X | O

RESULT: draw
```
