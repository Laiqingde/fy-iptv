# M3U 订阅代理，带鉴权和设备并发控制
#
# 访问地址：GET /m3u?token=<用户token>
#
# 校验流程：
#   1. token 有效且用户未被禁用
#   2. 订阅未过期
#   3. 每小时请求次数 ≤ RATE_LIMIT_HOUR（超出自动封号）
#   4. 记录本次请求的客户端 IP
#   5. 统计 DEVICE_WINDOW_MINUTES 分钟内活跃 IP 数 ≤ max_devices
#   6. 全部通过后返回 /var/www/m3u/playlist.m3u 内容

from fastapi import APIRouter, Request, Response, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
import models
from datetime import datetime, timedelta
from collections import defaultdict
import os

router = APIRouter(tags=["M3U"])

M3U_FILE = "/var/www/m3u/playlist.m3u"
DEVICE_WINDOW_MINUTES = 10   # 活跃设备时间窗口（分钟）
RATE_LIMIT_HOUR = 50         # 每个 token 每小时最大请求次数

# 进程内计数器，key=token，记录当前小时的请求次数
_rate = defaultdict(lambda: {"hour": -1, "count": 0})


def _check_rate(token: str) -> bool:
    h = datetime.utcnow().hour
    entry = _rate[token]
    if entry["hour"] != h:
        entry["hour"] = h
        entry["count"] = 0
    entry["count"] += 1
    return entry["count"] <= RATE_LIMIT_HOUR


def _get_client_ip(request: Request) -> str:
    # 优先取反代透传的真实 IP
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


@router.get("/m3u")
def serve_m3u(token: str, request: Request):
    db: Session = SessionLocal()
    try:
        user = db.query(models.User).filter_by(m3u_token=token, is_active=True).first()
        if not user:
            raise HTTPException(401, "无效的订阅地址")

        now = datetime.utcnow()
        if not user.expired_at or user.expired_at < now:
            raise HTTPException(403, "订阅已过期，请续费")

        if not _check_rate(token):
            # 触发频率限制，自动暂停账号（防中转滥用）
            user.is_active = False
            db.commit()
            raise HTTPException(429, "请求过于频繁，账号已暂停")

        ip = _get_client_ip(request)
        ua = request.headers.get("user-agent", "")[:256]
        cutoff = now - timedelta(minutes=DEVICE_WINDOW_MINUTES)

        # 更新或插入设备记录
        existing = db.query(models.DeviceLog).filter_by(user_id=user.id, ip=ip).first()
        if existing:
            existing.last_seen = now
            existing.user_agent = ua
        else:
            db.add(models.DeviceLog(user_id=user.id, ip=ip, user_agent=ua, last_seen=now))
        db.commit()

        # 统计时间窗口内的活跃 IP 数
        active_count = db.query(models.DeviceLog).filter(
            models.DeviceLog.user_id == user.id,
            models.DeviceLog.last_seen >= cutoff
        ).count()

        if active_count > user.max_devices:
            raise HTTPException(429, f"同时在线设备超过上限（{user.max_devices}个）")

        if not os.path.exists(M3U_FILE):
            raise HTTPException(503, "播放列表暂时不可用，请稍后重试")

        with open(M3U_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        return Response(content=content, media_type="application/x-mpegurl; charset=utf-8")
    finally:
        db.close()
