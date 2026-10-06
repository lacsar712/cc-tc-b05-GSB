import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from jose import JWTError, jwt
from passlib.context import CryptContext

from claimer import start as start_claimer
from models import (
    Base,
    ConvergenceLog,
    ShiftBriefing,
    SessionLocal,
    briefing_dict,
    engine,
    row_dict,
)

SECRET = os.environ.get("JWT_SECRET", "tunnelconv-dev-secret")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS = {
    "surveyor": {"role": "writer", "password_hash": pwd.hash("surv123456")},
    "inspector": {"role": "reader", "password_hash": pwd.hash("insp123456")},
}

app = Flask(__name__)


def seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(ConvergenceLog).count() > 0:
            return
        now = datetime.now(timezone.utc)
        for chainage, delta, expect in (("K12+180", 1.2, "合格"), ("K18+040", 5.6, "超限")):
            from rules import judge

            verdict, reason = judge(delta)
            assert verdict == expect
            db.add(
                ConvergenceLog(
                    chainage=chainage,
                    delta_mm=delta,
                    status="done",
                    verdict=verdict,
                    reason=reason,
                    created_by="surveyor",
                    created_at=now,
                    processed_at=now,
                )
            )
        db.commit()
    finally:
        db.close()


seed()
start_claimer()


def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:].strip(), SECRET, algorithms=["HS256"])
    except JWTError:
        return None
    sub = payload.get("sub")
    if sub not in USERS:
        return None
    return {"username": sub, "role": payload.get("role")}


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"detail": "未登录"}), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


def require_role(role, forbid_msg):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({"detail": "未登录"}), 401
            if user["role"] != role:
                return jsonify({"detail": forbid_msg}), 403
            g.user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_writer(fn):
    return require_role("writer", "仅测量员可提交收敛读数")(fn)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "tunnel-convergence-desk"})


@app.post("/api/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    user = USERS.get(username)
    if not user or not pwd.verify(password, user["password_hash"]):
        return jsonify({"detail": "用户名或密码错误"}), 401
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode(
        {"sub": username, "role": user["role"], "exp": exp}, SECRET, algorithm="HS256"
    )
    return jsonify({"access_token": token, "username": username, "role": user["role"]})


@app.get("/api/logs")
@require_login
def list_logs():
    db = SessionLocal()
    try:
        rows = db.query(ConvergenceLog).order_by(ConvergenceLog.id.desc()).all()
        return jsonify([row_dict(r) for r in rows])
    finally:
        db.close()


@app.post("/api/logs")
@require_writer
def create_log():
    body = request.get_json(silent=True) or {}
    chainage = (body.get("chainage") or "").strip()
    if not chainage:
        return jsonify({"detail": "桩号不能为空"}), 400
    try:
        delta_mm = float(body.get("delta_mm"))
    except (TypeError, ValueError):
        return jsonify({"detail": "收敛值必须是数字"}), 400
    db = SessionLocal()
    try:
        row = ConvergenceLog(
            chainage=chainage,
            delta_mm=delta_mm,
            status="pending",
            created_by=g.user["username"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify(row_dict(row)), 201
    finally:
        db.close()


RECENT_LIMIT = 5
BEIJING = timezone(timedelta(hours=8))


def shift_label_for(now_local: datetime) -> str:
    # 08:00–20:00 白班，其余夜班；标签完全由服务端按生成时刻决定
    kind = "白班" if 8 <= now_local.hour < 20 else "夜班"
    return f"{now_local.strftime('%Y-%m-%d')} {kind}"


def take_snapshot(db) -> dict:
    """按下生成瞬间的快照：一条聚合 SQL 取齐三项计数，再取最近几笔。

    计数不接受前端传参，巡检员也没有生成入口，杜绝手改数字充数。
    """
    from sqlalchemy import case, func, select

    done = ConvergenceLog.status == "done"
    stats = db.execute(
        select(
            func.count().label("total"),
            func.coalesce(
                func.sum(case((done & (ConvergenceLog.verdict == "合格"), 1), else_=0)), 0
            ).label("ok"),
            func.coalesce(
                func.sum(case((done & (ConvergenceLog.verdict == "超限"), 1), else_=0)), 0
            ).label("over"),
            func.coalesce(
                func.sum(case((ConvergenceLog.status == "pending", 1), else_=0)), 0
            ).label("pending"),
        )
    ).one()
    rows = (
        db.query(ConvergenceLog)
        .order_by(ConvergenceLog.id.desc())
        .limit(RECENT_LIMIT)
        .all()
    )
    recent = [
        {
            "id": r.id,
            "chainage": r.chainage,
            "delta_mm": r.delta_mm,
            "status": r.status,
            "verdict": r.verdict,
        }
        for r in rows
    ]
    return {
        "total": int(stats.total),
        "ok": int(stats.ok),
        "over": int(stats.over),
        "pending": int(stats.pending),
        "recent": recent,
    }


def render_body(snapshot: dict, shift_label: str, generated_at: datetime, username: str) -> str:
    local = generated_at.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "隧道收敛交班简报",
        f"班次：{shift_label}",
        f"生成时间：{local}（北京时间）",
        f"生成人：{username}",
        "",
        f"截至生成瞬间，收敛读数共 {snapshot['total']} 笔："
        f"合格 {snapshot['ok']} 笔，超限 {snapshot['over']} 笔，待判 {snapshot['pending']} 笔。",
        "",
        f"最近{RECENT_LIMIT}笔提要：",
    ]
    if snapshot["recent"]:
        for idx, r in enumerate(snapshot["recent"], 1):
            if r["status"] == "pending":
                conclusion = "待判"
            else:
                conclusion = r["verdict"] or "已完成"
            lines.append(
                f"{idx}. #{r['id']} {r['chainage']} {r['delta_mm']} mm，{conclusion}"
            )
    else:
        lines.append("（生成时一张单都没有，计数均为 0）")
    return "\n".join(lines)


@app.post("/api/briefings")
@require_role("writer", "巡检员只读已生成简报，不能生成交班简报")
def create_briefing():
    db = SessionLocal()
    try:
        # 统计与提要必须是认领线程无法插进来的同一瞬间：PG 上用事务快照，
        # 保证聚合计数和最近几笔看到的是同一个数据库版本。
        if engine.dialect.name == "postgresql":
            db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        now = datetime.now(timezone.utc)
        snapshot = take_snapshot(db)
        shift_label = shift_label_for(now.astimezone(BEIJING))
        body = render_body(snapshot, shift_label, now, g.user["username"])
        row = ShiftBriefing(
            shift_label=shift_label,
            ok_count=snapshot["ok"],
            over_count=snapshot["over"],
            pending_count=snapshot["pending"],
            total_count=snapshot["total"],
            recent=snapshot["recent"],
            body=body,
            generated_by=g.user["username"],
            generated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify(briefing_dict(row)), 201
    finally:
        db.close()


@app.get("/api/briefings")
@require_login
def list_briefings():
    db = SessionLocal()
    try:
        rows = db.query(ShiftBriefing).order_by(ShiftBriefing.id.desc()).all()
        return jsonify([briefing_dict(r) for r in rows])
    finally:
        db.close()


@app.get("/api/briefings/<int:briefing_id>")
@require_login
def get_briefing(briefing_id: int):
    db = SessionLocal()
    try:
        row = db.get(ShiftBriefing, briefing_id)
        if row is None:
            return jsonify({"detail": "简报不存在"}), 404
        return jsonify(briefing_dict(row))
    finally:
        db.close()
