from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

# 场次封闭状态：封闭（存在关键考生，必须全员落座）与开放（无关键考生，允许现网未排）互斥。
SESSION_OPEN = "open"
SESSION_CLOSED = "closed"
SESSION_STATES = (SESSION_OPEN, SESSION_CLOSED)

class Hall(Base):
    __tablename__ = "halls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    rows: Mapped[int] = mapped_column(Integer)
    cols: Mapped[int] = mapped_column(Integer)
    min_manhattan: Mapped[int] = mapped_column(Integer, default=2)

class PaperSet(Base):
    __tablename__ = "paper_sets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(128))

class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    name: Mapped[str] = mapped_column(String(64))
    ticket_no: Mapped[str] = mapped_column(String(32))
    paper_id: Mapped[int] = mapped_column(ForeignKey("paper_sets.id"))
    # 关键考生标记：只要存在一名关键考生，下一次提交排座场次即进入封闭。
    is_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class SeatPlan(Base):
    __tablename__ = "seat_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # 该次提交瞬间的场次状态：closed=封闭（未排入口关闭，未排必须为 0）；open=开放（允许现网未排）。
    session_status: Mapped[str] = mapped_column(String(8), default=SESSION_OPEN, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
