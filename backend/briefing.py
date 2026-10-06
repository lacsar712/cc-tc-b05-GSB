"""交班签出简报：按下生成瞬间的统计与最近几笔提要冻结成正文并入库。

正文只在此处由服务端组成，客户端不能提交自定义正文；
一旦写入 shift_briefings 表，任何线上数据变动都不再回改它。
"""
from datetime import datetime, timezone

from models import ConvergenceLog, ShiftBriefing

DIGEST_LIMIT = 3
LINE = "——————————————"


def _describe(row: ConvergenceLog) -> str:
    if row.status == "pending":
        state = "待办（未判定）"
    else:
        state = row.verdict or "已处理"
        if row.reason:
            state = f"{state}（{row.reason}）"
    return f"#{row.id} {row.chainage} 收敛 {row.delta_mm} mm：{state}"


def compose_body(
    briefing_id: int,
    generated_by: str,
    generated_at: datetime,
    qualified: int,
    overlimit: int,
    pending: int,
    total: int,
    recent: list,
) -> str:
    lines = [
        f"交班签出简报　第 {briefing_id} 号",
        f"生成时间：{generated_at.isoformat(timespec='seconds')}",
        f"生成人：{generated_by}",
        LINE,
        "当班统计（按下生成瞬间冻结）：",
        f"合格 {qualified} 笔　超限 {overlimit} 笔　待办 {pending} 笔　合计 {total} 笔",
        LINE,
        f"最近 {len(recent)} 笔提要：",
    ]
    if recent:
        lines.extend(f"- {_describe(r)}" for r in recent)
    else:
        lines.append("（当班无任何记录，计数为零）")
    lines += [
        LINE,
        "本简报为交班唯一冻结凭证，二衬交班同走此份，不另开旁路。",
        "正文已冻结入库，之后线上数据变动不影响以上数字。",
    ]
    return "\n".join(lines)


def freeze_briefing(db, username: str) -> ShiftBriefing:
    """统计当前 convergence_logs，生成并落库一份冻结简报。"""
    now = datetime.now(timezone.utc)
    qualified = (
        db.query(ConvergenceLog)
        .filter(ConvergenceLog.status == "done", ConvergenceLog.verdict == "合格")
        .count()
    )
    overlimit = (
        db.query(ConvergenceLog)
        .filter(ConvergenceLog.status == "done", ConvergenceLog.verdict == "超限")
        .count()
    )
    pending = db.query(ConvergenceLog).filter(ConvergenceLog.status == "pending").count()
    total = db.query(ConvergenceLog).count()
    recent = (
        db.query(ConvergenceLog)
        .order_by(ConvergenceLog.id.desc())
        .limit(DIGEST_LIMIT)
        .all()
    )

    row = ShiftBriefing(
        generated_by=username,
        generated_at=now,
        total_count=total,
        qualified_count=qualified,
        overlimit_count=overlimit,
        pending_count=pending,
        body="",  # 先占位，flush 拿到编号后写入冻结正文
    )
    db.add(row)
    db.flush()
    row.body = compose_body(
        row.id, username, now, qualified, overlimit, pending, total, recent
    )
    db.commit()
    db.refresh(row)
    return row
