import os
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DSN = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:54401/tunnelconv")
engine = create_engine(DSN, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class ConvergenceLog(Base):
    __tablename__ = "convergence_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chainage: Mapped[str] = mapped_column(String, nullable=False)
    delta_mm: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    verdict: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ShiftBriefing(Base):
    """交班冻结简报：按下生成瞬间的统计与最近提要，渲染成正文后整体落库。

    落库之后不再随 convergence_logs 变化而改动——历史清单打开看到的永远是
    生成那一刻的数字。
    """

    __tablename__ = "shift_briefings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_label: Mapped[str] = mapped_column(String, nullable=False)
    ok_count: Mapped[int] = mapped_column(Integer, nullable=False)
    over_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pending_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    recent: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    generated_by: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def row_dict(row: ConvergenceLog) -> dict:
    return {
        "id": row.id,
        "chainage": row.chainage,
        "delta_mm": row.delta_mm,
        "status": row.status,
        "verdict": row.verdict,
        "reason": row.reason,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }


def briefing_dict(row: ShiftBriefing) -> dict:
    return {
        "id": row.id,
        "shift_label": row.shift_label,
        "ok_count": row.ok_count,
        "over_count": row.over_count,
        "pending_count": row.pending_count,
        "total_count": row.total_count,
        "recent": row.recent or [],
        "body": row.body,
        "generated_by": row.generated_by,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
    }
