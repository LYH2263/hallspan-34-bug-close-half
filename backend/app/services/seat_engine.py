"""Exam seating: min Manhattan distance; same paper_id cannot be 4-neighbor adjacent.

场次状态（互斥，提交排座的瞬间按当前关键考生标记重算）：
- closed 封闭：存在至少一名关键考生，未排入口关闭，必须全员落座；做不到则整场失败。
- open 开放：没有任何关键标记，允许现网未排（部分考生未排上）。
不存在“普通人已坐但仍有未排”的半封闭状态。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

from app.models.models import SESSION_CLOSED, SESSION_OPEN

# 封闭场无法全员落座时的唯一失败说明；不得与缺考策略、考室不存在等并句。
CLOSED_MUST_SEAT_ALL = "封闭场必须全员落座"
# 封闭回溯的节点预算；耗尽即按失败处理，绝不退回半封闭结果。
_CLOSED_NODE_BUDGET = 50_000


class SeatingClosedError(Exception):
    """封闭场次做不到全员落座（整场失败，不产生方案）。"""

    def __init__(self, message: str = CLOSED_MUST_SEAT_ALL):
        super().__init__(message)
        self.message = message


@dataclass
class SeatAssign:
    candidate_id: int
    name: str
    ticket_no: str
    paper_id: int
    row: int
    col: int

@dataclass
class Violation:
    kind: str
    a_id: int
    b_id: int
    detail: str

def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def neighbors4(r: int, c: int, rows: int, cols: int) -> list[tuple[int, int]]:
    out = []
    for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            out.append((nr, nc))
    return out

def _seat_ok(r: int, c: int, rows: int, cols: int, min_dist: int,
             paper_id: int, occupied: dict[tuple[int, int], SeatAssign]) -> bool:
    """该座位对已落座者是否同时满足最小曼哈顿距离与同卷不四邻相邻。"""
    for pos, other in occupied.items():
        if manhattan((r, c), pos) < min_dist:
            return False
        if other.paper_id == paper_id and (r, c) in neighbors4(pos[0], pos[1], rows, cols):
            return False
    return True

def place_candidates(rows: int, cols: int, min_dist: int, candidates: list[dict]) -> tuple[list[SeatAssign], list[dict]]:
    """开放场贪心：逐行逐位试座，接受即落；放不下的进 unplaced（仅开放场允许）。"""
    occupied: dict[tuple[int, int], SeatAssign] = {}
    unplaced: list[dict] = []
    for cand in candidates:
        placed = False
        for r in range(rows):
            for c in range(cols):
                if (r, c) in occupied:
                    continue
                if not _seat_ok(r, c, rows, cols, min_dist, cand["paper_id"], occupied):
                    continue
                assign = SeatAssign(cand["id"], cand["name"], cand["ticket_no"], cand["paper_id"], r, c)
                occupied[(r, c)] = assign
                placed = True
                break
            if placed:
                break
        if not placed:
            unplaced.append(cand)
    return list(occupied.values()), unplaced

def _bipartite_independent_upper(vertices: set[tuple[int, int]],
                                 nbr4_index: dict[tuple[int, int], list[tuple[int, int]]]) -> int:
    """四邻网格图（二部图）在给定顶点子集上的独立数上界 α=|V|-ν（König），Kuhn 求 ν。

    任何满足“相邻格不同时坐人”的方案人数都不超过该独立集大小，故该值是 admissible 上界。
    """
    def augment(v: tuple[int, int], seen: set[tuple[int, int]],
                match: dict[tuple[int, int], tuple[int, int]]) -> bool:
        for w in nbr4_index[v]:
            if w not in vertices or w in seen:
                continue
            seen.add(w)
            if w not in match or augment(match[w], seen, match):
                match[w] = v
                return True
        return False

    match: dict[tuple[int, int], tuple[int, int]] = {}
    matching = 0
    for v in vertices:
        if (v[0] + v[1]) % 2 == 0 and augment(v, set(), match):
            matching += 1
    return len(vertices) - matching

def place_all_closed(rows: int, cols: int, min_dist: int, candidates: list[dict]) -> list[SeatAssign]:
    """封闭场：全员必须落座。

    同一卷别的考生可互换，因此搜索“格位标签”：每格标成某卷别或空座，
    带卷别配额（空座配额=格位-人数）。标签可行需满足：两个非空标签
    曼哈顿距离 ≥ min_dist，且同卷不四邻相邻。MRV 选合法标签最少的格。
    先跑一遍开放贪心作为快速路径；搜索仍做不到（含预算耗尽）则整场失败。
    """
    total_cells = rows * cols
    if len(candidates) > total_cells:
        raise SeatingClosedError()
    assigns, unplaced = place_candidates(rows, cols, min_dist, candidates)
    if not unplaced:
        return assigns

    empty_label = -1
    quotas: dict[int, int] = {}
    for cand in candidates:
        p = cand["paper_id"]
        quotas[p] = quotas.get(p, 0) + 1
    quotas[empty_label] = total_cells - len(candidates)
    all_cells = [(r, c) for r in range(rows) for c in range(cols)]
    nbr4_index = {cell: neighbors4(cell[0], cell[1], rows, cols) for cell in all_cells}
    near_index = {
        cell: [w for w in all_cells if w != cell and manhattan(cell, w) < min_dist]
        for cell in all_cells
    }
    grid: dict[tuple[int, int], int] = {}
    budget = _CLOSED_NODE_BUDGET

    def radius_cells(r: int, c: int) -> list[tuple[int, int]]:
        # 距离约束只需查 min_dist-1 切比雪夫半径；半径至少 1 以覆盖同卷四邻检查。
        radius = max(1, min_dist - 1)
        return [(rr, cc)
                for rr in range(max(0, r - radius), min(rows, r + radius + 1))
                for cc in range(max(0, c - radius), min(cols, c + radius + 1))
                if (rr, cc) != (r, c)]

    def legal_labels(cell: tuple[int, int]) -> list[int]:
        r, c = cell
        labels = [p for p, n in quotas.items() if n > 0]
        out = []
        for label in labels:
            ok = True
            for pos in radius_cells(r, c):
                other = grid.get(pos)
                if other is None or other == empty_label or label == empty_label:
                    continue
                d = manhattan((r, c), pos)
                if d < min_dist:  # 两名落座者间距不足
                    ok = False
                    break
                if other == label and d == 1:  # min_dist=1 时同卷仍不得四邻
                    ok = False
                    break
            if ok:
                out.append(label)
        return out

    def dfs() -> bool:
        nonlocal budget
        budget -= 1
        if budget < 0:
            return False  # 预算耗尽按失败处理：封闭场宁可整场失败，也不产出半封闭
        unassigned = [cell for cell in all_cells if cell not in grid]
        if not unassigned:
            return True
        seated_positions = [pos for pos, label in grid.items() if label != empty_label]
        remaining_people = sum(n for p, n in quotas.items() if p != empty_label)
        if min_dist >= 2:
            # 距离约束（≥2 含四邻）：未来落座者只能落在与已坐者距离合法的格里，
            # 且彼此四邻不相邻——剩余人数不得超过可用格诱导子图的独立数。
            blocked: set[tuple[int, int]] = set()
            for pos in seated_positions:
                blocked.update(near_index[pos])
            available = {cell for cell in unassigned if cell not in blocked}
            if remaining_people > _bipartite_independent_upper(available, nbr4_index):
                return False
        else:
            # min_dist=1：距离无限制，但每种卷别剩余人数不得超过
            # “无同卷四邻”可用格诱导子图的独立数。
            for p, n in quotas.items():
                if p == empty_label or n <= 0:
                    continue
                blocked_p: set[tuple[int, int]] = set()
                for pos, label in grid.items():
                    if label == p:
                        blocked_p.update(nbr4_index[pos])
                available_p = {cell for cell in unassigned if cell not in blocked_p}
                if n > _bipartite_independent_upper(available_p, nbr4_index):
                    return False
        # MRV：合法标签最少的未填格；顺带得到每格合法标签做存活剪枝。
        domains: list[tuple[tuple[int, int], list[int]]] = []
        for cell in unassigned:
            dom = legal_labels(cell)
            if not dom:
                return False
            domains.append((cell, dom))
        for label, n in quotas.items():
            if n > 0 and not any(label in dom for _, dom in domains):
                return False  # 该卷别/空座已无处可放
        cell, dom = min(domains, key=lambda x: len(x[1]))
        # 有配额的卷别优先（配额多的先放），空座最后。
        for label in sorted(dom, key=lambda p: (p == empty_label, -quotas[p])):
            grid[cell] = label
            quotas[label] -= 1
            if dfs():
                return True
            quotas[label] += 1
            del grid[cell]
        return False

    if not dfs():
        raise SeatingClosedError()
    # 同卷考生可互换：按名册顺序把候选人贴到对应卷别的格位上（格位按行列序）。
    by_paper: dict[int, list[dict]] = {}
    for cand in candidates:
        by_paper.setdefault(cand["paper_id"], []).append(cand)
    seats_by_paper: dict[int, list[tuple[int, int]]] = {}
    for (r, c), label in grid.items():
        if label != empty_label:
            seats_by_paper.setdefault(label, []).append((r, c))
    out: list[SeatAssign] = []
    for p, seats in seats_by_paper.items():
        seats.sort()
        for cand, (r, c) in zip(by_paper[p], seats):
            out.append(SeatAssign(cand["id"], cand["name"], cand["ticket_no"], cand["paper_id"], r, c))
    return out

def run_session(rows: int, cols: int, min_dist: int, candidates: list[dict]) -> tuple[str, list[SeatAssign], list[dict]]:
    """按当次提交瞬间的关键标记决定场次状态并排座。

    返回 (session_status, assignments, unplaced)：
    - 有关键考生 → closed，全员落座，unplaced 必为 []；做不到抛 SeatingClosedError；
    - 无关键考生 → open，允许现网未排。
    """
    if any(c["is_key"] for c in candidates):
        # 封闭场：全员落座，unplaced 恒为 []；做不到由 place_all_closed 抛
        # SeatingClosedError（整场失败、不返回半封闭）。关键标记不要求前排格位。
        assigns = place_all_closed(rows, cols, min_dist, candidates)
        return SESSION_CLOSED, assigns, []
    assigns, unplaced = place_candidates(rows, cols, min_dist, candidates)
    return SESSION_OPEN, assigns, unplaced

def find_violations(rows: int, cols: int, min_dist: int, assigns: list[SeatAssign]) -> list[Violation]:
    viols: list[Violation] = []
    for i, a in enumerate(assigns):
        for b in assigns[i + 1:]:
            d = manhattan((a.row, a.col), (b.row, b.col))
            if d < min_dist:
                viols.append(Violation("distance", a.candidate_id, b.candidate_id,
                                       f"曼哈顿距离 {d} < 最小要求 {min_dist}"))
            if a.paper_id == b.paper_id and (b.row, b.col) in neighbors4(a.row, a.col, rows, cols):
                viols.append(Violation("same_paper_adjacent", a.candidate_id, b.candidate_id,
                                       f"同试卷套 {a.paper_id} 四邻相邻"))
    return viols

def plan_to_dict(assigns: list[SeatAssign], unplaced: list[dict], viols: list[Violation],
                 rows: int, cols: int, session_status: str = SESSION_OPEN) -> dict:
    # 封闭与开放互斥：封闭场未排入口关闭，未排统计必须为 0，绝不写出半封闭。
    if session_status == SESSION_CLOSED:
        assert not unplaced, "closed session must seat every candidate"
        unplaced_out: list[dict] = []
    else:
        unplaced_out = unplaced
    return {
        "session_status": session_status,
        "rows": rows,
        "cols": cols,
        "assignments": [asdict(a) for a in assigns],
        "unplaced": unplaced_out,
        "violations": [asdict(v) for v in viols],
        "stats": {
            "session_status": session_status,
            "seated": len(assigns),
            "unplaced": len(unplaced_out),
            "violations": len(viols),
            "capacity": rows * cols,
        },
    }
