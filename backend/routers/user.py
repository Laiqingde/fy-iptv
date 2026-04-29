# 用户路由
#
# POST /api/user/register  - 注册（支持开放注册和邀请码两种模式，由 config.json 控制）
# POST /api/user/login     - 登录，返回 JWT token
# GET  /api/user/me        - 获取当前用户信息（订阅状态、活跃设备、M3U 地址）
# POST /api/user/reset-token - 重置 M3U token（旧地址立即失效）

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
import models, auth, config
from datetime import datetime, timedelta
import secrets

router = APIRouter(tags=["用户"])


class RegisterIn(BaseModel):
    username: str
    password: str
    invite_code: str = ""


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if len(body.username) < 3 or len(body.password) < 6:
        raise HTTPException(400, "用户名至少3位，密码至少6位")
    if db.query(models.User).filter_by(username=body.username).first():
        raise HTTPException(400, "用户名已存在")

    reg_mode = config.REGISTRATION.get('mode', 'open')
    used_code = None
    if reg_mode == 'invite' or body.invite_code:
        if not body.invite_code:
            raise HTTPException(400, "需要邀请码")
        code = db.query(models.InviteCode).filter_by(code=body.invite_code).first()
        if not code or code.use_count >= code.max_uses:
            raise HTTPException(400, "邀请码无效或已用完")
        code.use_count += 1
        used_code = body.invite_code

    user = models.User(
        username=body.username,
        password_hash=auth.hash_password(body.password),
        m3u_token=secrets.token_hex(24),
        invite_code_used=used_code,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": auth.create_token(user.id), "username": user.username, "is_admin": user.is_admin}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(username=body.username).first()
    if not user or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    if not user.is_active:
        raise HTTPException(403, "账号已被禁用")
    return {"token": auth.create_token(user.id), "username": user.username, "is_admin": user.is_admin}


@router.get("/me")
def me(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    expired = user.expired_at
    days_left = max(0, (expired - now).days) if expired else 0
    is_expired = (not expired) or (expired < now)

    cutoff = now - timedelta(minutes=10)
    devices = db.query(models.DeviceLog).filter(
        models.DeviceLog.user_id == user.id,
        models.DeviceLog.last_seen >= cutoff
    ).all()

    m3u_url = f"{config.APP['base_url']}/m3u?token={user.m3u_token}"
    return {
        "id": user.id,
        "username": user.username,
        "m3u_token": user.m3u_token,
        "m3u_url": m3u_url,
        "expired_at": expired.isoformat() if expired else None,
        "days_left": days_left,
        "is_expired": is_expired,
        "max_devices": user.max_devices,
        "is_admin": user.is_admin,
        "active_devices": [{"ip": d.ip, "last_seen": d.last_seen.isoformat()} for d in devices],
    }


@router.post("/reset-token")
def reset_token(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    user.m3u_token = secrets.token_hex(24)
    db.commit()
    return {"m3u_token": user.m3u_token, "m3u_url": f"{config.APP['base_url']}/m3u?token={user.m3u_token}"}
