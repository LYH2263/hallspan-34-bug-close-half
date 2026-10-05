import pytest

from app.services.seat_engine import (
    CLOSED_MUST_SEAT_ALL,
    SeatingClosedError,
    SeatAssign,
    find_violations,
    manhattan,
    place_all_closed,
    place_candidates,
    plan_to_dict,
    run_session,
)
from app.models.models import SESSION_CLOSED, SESSION_OPEN


def _cands(n, key_ids=(), papers=None):
    return [
        {"id": i, "name": f"C{i}", "ticket_no": f"T{i}",
         "paper_id": (papers[i - 1] if papers else 1 + (i % 3)),
         "is_key": i in key_ids}
        for i in range(1, n + 1)
    ]


def test_manhattan():
    assert manhattan((0, 0), (2, 1)) == 3


def test_min_distance_placement():
    cands = [{"id": i, "name": f"C{i}", "ticket_no": f"T{i}", "paper_id": 1 + (i % 2)} for i in range(4)]
    assigns, unplaced = place_candidates(4, 4, 2, cands)
    assert len(assigns) + len(unplaced) == 4
    for i, a in enumerate(assigns):
        for b in assigns[i + 1:]:
            assert manhattan((a.row, a.col), (b.row, b.col)) >= 2


def test_same_paper_not_adjacent_in_result():
    cands = [
        {"id": 1, "name": "A", "ticket_no": "T1", "paper_id": 1},
        {"id": 2, "name": "B", "ticket_no": "T2", "paper_id": 1},
        {"id": 3, "name": "C", "ticket_no": "T3", "paper_id": 2},
    ]
    assigns, _ = place_candidates(3, 3, 1, cands)
    viols = find_violations(3, 3, 1, assigns)
    assert not any(v.kind == "same_paper_adjacent" for v in viols)


def test_violation_detection():
    assigns = [
        SeatAssign(1, "A", "T1", 1, 0, 0),
        SeatAssign(2, "B", "T2", 1, 0, 1),
    ]
    viols = find_violations(2, 2, 2, assigns)
    kinds = {v.kind for v in viols}
    assert "distance" in kinds
    assert "same_paper_adjacent" in kinds


def test_key_candidate_with_tight_grid_fails_entire_session():
    # 4x5、最小距离 2 时最多坐 10 人；12 人且有一名关键考生 -> 整场失败。
    cands = _cands(12, key_ids={1})
    with pytest.raises(SeatingClosedError) as exc:
        run_session(4, 5, 2, cands)
    assert str(exc.value.message) == CLOSED_MUST_SEAT_ALL == "封闭场必须全员落座"


def test_closed_failure_never_returns_half_seated_plan():
    cands = _cands(12, key_ids={1})
    with pytest.raises(SeatingClosedError):
        place_all_closed(4, 5, 2, cands)  # 不返回“普通人已坐但仍有未排”的半封闭结果


def test_no_key_flag_means_open_and_allows_partial_unplaced():
    # 去掉全部关键标记后：开放，允许现网未排（10 落座 / 2 未排）。
    cands = _cands(12)
    status, assigns, unplaced = run_session(4, 5, 2, cands)
    assert status == SESSION_OPEN
    assert len(assigns) == 10
    assert len(unplaced) == 2
    assert not find_violations(4, 5, 2, assigns)


def test_closed_success_seats_all_with_zero_unplaced():
    cands = _cands(10, key_ids={1})
    status, assigns, unplaced = run_session(4, 5, 2, cands)
    assert status == SESSION_CLOSED
    assert len(assigns) == 10
    assert unplaced == []
    assert not find_violations(4, 5, 2, assigns)


def test_closed_dict_never_serializes_unplaced():
    cands = _cands(10, key_ids={1})
    _, assigns, _ = run_session(4, 5, 2, cands)
    data = plan_to_dict(assigns, [], [], 4, 5, SESSION_CLOSED)
    assert data["session_status"] == SESSION_CLOSED
    assert data["unplaced"] == []
    assert data["stats"]["unplaced"] == 0
    with pytest.raises(AssertionError):
        plan_to_dict(assigns, [{"id": 99}], [], 4, 5, SESSION_CLOSED)


def test_open_dict_keeps_unplaced():
    cands = _cands(12)
    _, assigns, unplaced = run_session(4, 5, 2, cands)
    data = plan_to_dict(assigns, unplaced, [], 4, 5, SESSION_OPEN)
    assert data["session_status"] == SESSION_OPEN
    assert data["stats"]["unplaced"] == 2


def test_state_flips_at_each_submission_not_from_stale_graph():
    cands = _cands(12)
    status, _, _ = run_session(4, 5, 2, cands)
    assert status == SESSION_OPEN  # 无关键标记 -> 开放
    cands[0]["is_key"] = True
    with pytest.raises(SeatingClosedError):
        run_session(4, 5, 2, cands)  # 下一次提交瞬间切封闭，旧开放图不得沿用
    cands[0]["is_key"] = False
    status, _, unplaced = run_session(4, 5, 2, cands)
    assert status == SESSION_OPEN and len(unplaced) == 2  # 再去标记又切回开放


def test_closed_does_not_require_front_rows():
    # 规则只要求全员落座，不规定必须坐前排：4x4 坐 4 人时允许出现在后排格位。
    cands = _cands(4, key_ids={1})
    _, assigns, _ = run_session(4, 4, 2, cands)
    assert len(assigns) == 4  # 不强制前排，只要全员落座即成功


def test_closed_over_capacity_fails_with_clean_message():
    cands = _cands(5, key_ids={1})
    with pytest.raises(SeatingClosedError) as exc:
        run_session(2, 2, 1, cands)
    assert exc.value.message == "封闭场必须全员落座"
