import re

EMPTY = "."
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


class IllegalMove(ValueError):
    pass


def other(mark: str) -> str:
    return "O" if mark == "X" else "X"


class Board:
    def __init__(self, cells: str = EMPTY * 9):
        cells = cells.replace(" ", "").replace("\n", "").replace("-", EMPTY).replace("_", EMPTY)
        if len(cells) != 9 or set(cells) - {"X", "O", EMPTY}:
            raise ValueError(f"bad board string: {cells!r}")
        self.cells = list(cells)

    def __str__(self) -> str:
        return "".join(self.cells)

    def copy(self) -> "Board":
        return Board(str(self))

    def legal_moves(self) -> list[int]:
        if self.winner():
            return []
        return [i + 1 for i, c in enumerate(self.cells) if c == EMPTY]

    def to_move(self) -> str:
        return "X" if self.cells.count("X") == self.cells.count("O") else "O"

    def play(self, cell: int, mark: str | None = None) -> None:
        mark = mark or self.to_move()
        if not isinstance(cell, int) or not 1 <= cell <= 9:
            raise IllegalMove(f"cell {cell!r} is out of range; pick 1-9")
        if self.cells[cell - 1] != EMPTY:
            raise IllegalMove(f"cell {cell} is already taken by {self.cells[cell - 1]}")
        if self.winner():
            raise IllegalMove("game is already over")
        self.cells[cell - 1] = mark

    def winner(self) -> str | None:
        for a, b, c in LINES:
            if self.cells[a] != EMPTY and self.cells[a] == self.cells[b] == self.cells[c]:
                return self.cells[a]
        return None

    def full(self) -> bool:
        return EMPTY not in self.cells

    def over(self) -> bool:
        return self.winner() is not None or self.full()

    def pretty(self) -> str:
        show = [c if c != EMPTY else str(i + 1) for i, c in enumerate(self.cells)]
        rows = [" " + " | ".join(show[r * 3:r * 3 + 3]) for r in range(3)]
        return "\n---+---+---\n".join(rows)


_ROWCOL = re.compile(r"row\s*[:=]?\s*(-?\d+)\D+?col(?:umn)?\s*[:=]?\s*(-?\d+)", re.I)
_PAIR = re.compile(r"^\s*\(?\s*(-?\d+)\s*,\s*(-?\d+)\s*\)?\s*$")


def parse_move(move) -> int:
    if isinstance(move, bool):
        raise IllegalMove(f"not a move: {move!r}")
    if isinstance(move, dict):
        if "row" in move and ("col" in move or "column" in move):
            return _from_rowcol(move["row"], move.get("col", move.get("column")))
        if "cell" in move:
            return parse_move(move["cell"])
        raise IllegalMove(f"could not read a move from {move!r}")
    if isinstance(move, float) and move.is_integer():
        move = int(move)
    if isinstance(move, int):
        if not 1 <= move <= 9:
            raise IllegalMove(f"cell {move} is out of range; pick 1-9")
        return move
    text = str(move).strip()
    m = _ROWCOL.search(text) or _PAIR.match(text)
    if m:
        return _from_rowcol(m.group(1), m.group(2))
    nums = re.findall(r"-?\d+", text)
    if len(nums) == 1:
        return parse_move(int(nums[0]))
    raise IllegalMove(f"could not read a move from {text[:60]!r}")


def _from_rowcol(row, col) -> int:
    try:
        r, c = int(row), int(col)
    except (TypeError, ValueError):
        raise IllegalMove(f"row/col must be numbers, got {row!r}, {col!r}") from None
    if not (1 <= r <= 3 and 1 <= c <= 3):
        raise IllegalMove(f"row {r}, col {c} is off the board; rows and columns are 1-3")
    return (r - 1) * 3 + c
