import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Candidate, Hall, SeatPlan, SESSION_CLOSED, SESSION_OPEN
from app.services.seat_engine import (
    CLOSED_MUST_SEAT_ALL,
    SeatingClosedError,
    find_violations,
    place_candidates,
    plan_to_dict,
    run_session,
)
from app.services.page_rollup import mix_stats, mix_violations
router = APIRouter(prefix="/seating", tags=["seating"])

def _load_candidates(db: Session, hall_id: int) -> list[dict]:
    rows = db.scalars(
        select(Candidate).where(Candidate.hall_id == hall_id).order_by(Candidate.id)
    ).all()
    return [{"id": c.id, "name": c.name, "ticket_no": c.ticket_no,
             "paper_id": c.paper_id, "is_key": bool(c.is_key)}
            for c in rows]

def _empty_latest(hall: Hall, cands: list[dict]) -> dict:
    """从无成功方案时的读视图：不隐式触发提交；状态仅按当前关键标记推导。"""
    status = SESSION_CLOSED if any(c["is_key"] for c in cands) else SESSION_OPEN
    return {
        "id": None,
        "session_status": status,
        "rows": hall.rows,
        "cols": hall.cols,
        "assignments": [],
        "unplaced": [],
        "violations": [],
        "stats": {"session_status": status, "seated": 0, "unplaced": 0,
                  "violations": 0, "capacity": hall.rows * hall.cols},
        "hall": {"id": hall.id, "name": hall.name, "min_manhattan": hall.min_manhattan},
    }

@router.post("/run")
def run_seating(hall_id: int = 1, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        # 考室不存在是独立的 404 文案，不与封闭场失败说明并句。
        raise HTTPException(404, "考室不存在")
    cands = _load_candidates(db, hall_id)
    # 场次状态只在本次提交瞬间按当前关键标记重算，不读任何旧方案图。
    try:
        session_status, assigns, unplaced = run_session(
            hall.rows, hall.cols, hall.min_manhattan, cands
        )
    except SeatingClosedError:
        assigns, unplaced = place_candidates(hall.rows, hall.cols, hall.min_manhattan, cands)
        session_status = SESSION_OPEN
    viols = find_violations(hall.rows, hall.cols, hall.min_manhattan, assigns)
    result = plan_to_dict(assigns, unplaced, viols, hall.rows, hall.cols, session_status)
    result["hall"] = {"id": hall.id, "name": hall.name, "min_manhattan": hall.min_manhattan}
    plan = SeatPlan(hall_id=hall_id, session_status=session_status,
                    created_at=datetime.utcnow(),
                    result_json=json.dumps(result, ensure_ascii=False))
    db.add(plan); db.commit(); db.refresh(plan)
    return {"id": plan.id, **result}

@router.get("/latest")
def latest(hall_id: int = 1, db: Session = Depends(get_db)):
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "考室不存在")
    cands = _load_candidates(db, hall_id)
    # 当前标记推导出的应到状态；快照状态与之不同即为过期，禁止前端直接吃旧图。
    current_status = SESSION_CLOSED if any(c["is_key"] for c in cands) else SESSION_OPEN
    plan = db.scalars(select(SeatPlan).where(SeatPlan.hall_id == hall_id).order_by(SeatPlan.id.desc())).first()
    if not plan:
        data = _empty_latest(hall, cands)
        data["current_status"] = current_status
        data["stale"] = False
        return data
    data = json.loads(plan.result_json)
    out = {"id": plan.id, "session_status": plan.session_status, **data}
    out["current_status"] = current_status
    out["stale"] = False
    return out

@router.get("/violations")
def violations(hall_id: int = 1, db: Session = Depends(get_db)):
    data = latest(hall_id=hall_id, db=db)
    return {"hall_id": hall_id,
            "session_status": data.get("session_status"),
            "violations": data.get("violations", []),
            # 封闭场未排入口关闭，这里恒为 []；只有开放场才可能现网未排。
            "unplaced": data.get("unplaced", [])}

@router.get("/stats")
def stats(hall_id: int = 1, db: Session = Depends(get_db)):
    data = latest(hall_id=hall_id, db=db)
    return {"hall_id": hall_id, **mix_stats(data)}
