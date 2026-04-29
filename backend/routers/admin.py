from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
import models, auth
from datetime import datetime, timedelta
import secrets

router = APIRouter(tags=["管理"])


# ── Users ──────────────────────────────────────────────

@router.get("/users")
def list_users(page: int = 1, q: str = "", db: Session = Depends(get_db),
               _=Depends(auth.require_admin)):
    query = db.query(models.User)
    if q:
        query = query.filter(models.User.username.contains(q))
    total = query.count()
    users = query.order_by(models.User.created_at.desc()).offset((page-1)*20).limit(20).all()
    now = datetime.utcnow()
    return {
        "total": total,
        "users": [{
            "id": u.id, "username": u.username,
            "expired_at": u.expired_at.isoformat() if u.expired_at else None,
            "days_left": max(0, (u.expired_at - now).days) if u.expired_at and u.expired_at > now else 0,
            "max_devices": u.max_devices, "is_active": u.is_active, "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat(),
        } for u in users]
    }


class UserEditIn(BaseModel):
    add_days: Optional[int] = None
    max_devices: Optional[int] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


@router.patch("/users/{uid}")
def edit_user(uid: int, body: UserEditIn, db: Session = Depends(get_db),
              _=Depends(auth.require_admin)):
    user = db.query(models.User).filter_by(id=uid).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    now = datetime.utcnow()
    if body.add_days is not None:
        base = user.expired_at if user.expired_at and user.expired_at > now else now
        user.expired_at = base + timedelta(days=body.add_days)
    if body.max_devices is not None:
        user.max_devices = body.max_devices
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    db.commit()
    return {"ok": True}


@router.post("/users/{uid}/reset-token")
def admin_reset_token(uid: int, db: Session = Depends(get_db), _=Depends(auth.require_admin)):
    user = db.query(models.User).filter_by(id=uid).first()
    if not user:
        raise HTTPException(404)
    user.m3u_token = secrets.token_hex(24)
    db.commit()
    return {"m3u_token": user.m3u_token}


# ── Plans ──────────────────────────────────────────────

class PlanIn(BaseModel):
    name: str
    price: float
    duration_days: int
    description: Optional[str] = None
    sort_order: int = 0


@router.get("/plans")
def list_plans(db: Session = Depends(get_db), _=Depends(auth.require_admin)):
    return db.query(models.Plan).order_by(models.Plan.sort_order).all()


@router.post("/plans")
def create_plan(body: PlanIn, db: Session = Depends(get_db), _=Depends(auth.require_admin)):
    plan = models.Plan(**body.dict())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.patch("/plans/{pid}")
def update_plan(pid: int, body: PlanIn, db: Session = Depends(get_db), _=Depends(auth.require_admin)):
    plan = db.query(models.Plan).filter_by(id=pid).first()
    if not plan:
        raise HTTPException(404)
    for k, v in body.dict(exclude_unset=True).items():
        setattr(plan, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/plans/{pid}")
def delete_plan(pid: int, db: Session = Depends(get_db), _=Depends(auth.require_admin)):
    plan = db.query(models.Plan).filter_by(id=pid).first()
    if not plan:
        raise HTTPException(404)
    plan.is_active = False
    db.commit()
    return {"ok": True}


# ── Invite Codes ────────────────────────────────────────

class InviteIn(BaseModel):
    count: int = 1
    max_uses: int = 1
    note: Optional[str] = None


@router.post("/invites")
def gen_invites(body: InviteIn, user: models.User = Depends(auth.require_admin),
                db: Session = Depends(get_db)):
    codes = []
    for _ in range(min(body.count, 50)):
        code = secrets.token_hex(8).upper()
        db.add(models.InviteCode(code=code, max_uses=body.max_uses,
                                  created_by=user.id, note=body.note))
        codes.append(code)
    db.commit()
    return {"codes": codes}


@router.get("/invites")
def list_invites(db: Session = Depends(get_db), _=Depends(auth.require_admin)):
    items = db.query(models.InviteCode).order_by(models.InviteCode.created_at.desc()).limit(100).all()
    return [{"id": i.id, "code": i.code, "max_uses": i.max_uses, "use_count": i.use_count,
             "note": i.note, "created_at": i.created_at.isoformat()} for i in items]


# ── Orders ──────────────────────────────────────────────

@router.get("/orders")
def list_orders(page: int = 1, db: Session = Depends(get_db), _=Depends(auth.require_admin)):
    total = db.query(models.Order).count()
    orders = (db.query(models.Order, models.User.username)
              .join(models.User, models.Order.user_id == models.User.id)
              .order_by(models.Order.created_at.desc())
              .offset((page-1)*20).limit(20).all())
    return {
        "total": total,
        "orders": [{
            "out_trade_no": o.out_trade_no, "username": uname,
            "amount": o.amount, "duration_days": o.duration_days,
            "status": o.status, "payment_type": o.payment_type,
            "created_at": o.created_at.isoformat(),
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        } for o, uname in orders]
    }


# ── Stats ────────────────────────────────────────────────

@router.get("/stats")
def stats(db: Session = Depends(get_db), _=Depends(auth.require_admin)):
    now = datetime.utcnow()
    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(
        models.User.expired_at > now, models.User.is_active == True).count()
    total_orders = db.query(models.Order).filter_by(status=1).count()
    from sqlalchemy import func
    revenue = db.query(func.sum(models.Order.amount)).filter_by(status=1).scalar() or 0
    return {"total_users": total_users, "active_users": active_users,
            "total_orders": total_orders, "revenue": round(revenue, 2)}
