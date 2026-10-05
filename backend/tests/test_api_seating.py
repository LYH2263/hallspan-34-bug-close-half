import os
import tempfile

import pytest

# 必须在导入 app.* 之前指定 sqlite 测试库。
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["SEED_ON_EMPTY"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import Candidate, Hall, PaperSet  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        hall = Hall(code="H1", name="紧张考室", rows=4, cols=5, min_manhattan=2)
        big = Hall(code="H2", name="宽松考室", rows=6, cols=6, min_manhattan=2)
        db.add_all([hall, big]); db.flush()
        papers = [PaperSet(code=f"P{i}", title=f"卷{i}") for i in range(3)]
        db.add_all(papers); db.flush()
        for i in range(12):  # 4x5 有效容量 10，12 人格位紧张
            db.add(Candidate(hall_id=hall.id, name=f"考{i}", ticket_no=f"T{i}",
                             paper_id=papers[i % 3].id, is_key=(i == 0)))
        for i in range(10):
            db.add(Candidate(hall_id=big.id, name=f"宽{i}", ticket_no=f"W{i}",
                             paper_id=papers[i % 3].id, is_key=(i == 0)))
        db.commit()
    finally:
        db.close()
    with TestClient(app) as c:
        yield c


def _plan_count() -> int:
    from app.models.models import SeatPlan
    db = SessionLocal()
    try:
        n = db.query(SeatPlan).count()
    finally:
        db.close()
    return n


def test_closed_tight_grid_submission_fails_without_adding_plan(client):
    assert _plan_count() == 0
    r = client.post("/api/seating/run?hall_id=1")
    assert r.status_code == 422
    detail = r.json()["detail"]
    # 失败说明只写封闭场规则，不与缺考策略、考室不存在并句。
    assert detail == "封闭场必须全员落座"
    assert "缺考" not in detail and "考室" not in detail
    assert _plan_count() == 0  # 整场失败，不增方案


def test_remove_all_key_flags_then_open_allows_partial_unplaced(client):
    for c in client.get("/api/candidates").json():
        if c["is_key"]:
            client.patch(f"/api/candidates/{c['id']}", json={"is_key": False})
    r = client.post("/api/seating/run?hall_id=1")
    assert r.status_code == 200
    data = r.json()
    assert data["session_status"] == "open"
    assert data["stats"]["unplaced"] == 2
    assert len(data["unplaced"]) == 2
    assert _plan_count() == 1


def test_re_flag_closes_session_and_failure_keeps_old_plan_untouched(client):
    # 先得到一份开放方案。
    for c in client.get("/api/candidates").json():
        if c["is_key"]:
            client.patch(f"/api/candidates/{c['id']}", json={"is_key": False})
    client.post("/api/seating/run?hall_id=1")
    assert _plan_count() == 1
    # 重新标记一名关键考生：latest 必须提示当前应为封闭、快照已过期。
    first = client.get("/api/candidates").json()[0]
    client.patch(f"/api/candidates/{first['id']}", json={"is_key": True})
    latest = client.get("/api/seating/latest?hall_id=1").json()
    assert latest["current_status"] == "closed"
    assert latest["stale"] is True  # 禁止直接吃旧开放图
    # 再提交：封闭失败，方案数不增加。
    r = client.post("/api/seating/run?hall_id=1")
    assert r.status_code == 422
    assert r.json()["detail"] == "封闭场必须全员落座"
    assert _plan_count() == 1
    # 旧快照仍是 open（没有被失败改写），但 stale 仍在。
    latest = client.get("/api/seating/latest?hall_id=1").json()
    assert latest["session_status"] == "open"
    assert latest["current_status"] == "closed"
    assert latest["stale"] is True


def test_closed_with_enough_room_succeeds_zero_unplaced(client):
    r = client.post("/api/seating/run?hall_id=2")  # 6x6 容量 18，坐 10 人
    assert r.status_code == 200
    data = r.json()
    assert data["session_status"] == "closed"
    assert data["stats"]["unplaced"] == 0
    assert len(data["assignments"]) == 10
    assert data["unplaced"] == []


def test_states_are_mutex_and_stats_reflect_state(client):
    ok = client.post("/api/seating/run?hall_id=2").json()
    assert ok["stats"]["session_status"] == ok["session_status"] == "closed"
    # 违规接口在封闭场不暴露未排入口。
    v = client.get("/api/seating/violations?hall_id=2").json()
    assert v["session_status"] == "closed" and v["unplaced"] == []


def test_missing_hall_message_is_separate_from_closed_rule(client):
    r = client.post("/api/seating/run?hall_id=999")
    assert r.status_code == 404
    assert r.json()["detail"] == "考室不存在"


def test_patch_unknown_candidate_404(client):
    r = client.patch("/api/candidates/9999", json={"is_key": True})
    assert r.status_code == 404
