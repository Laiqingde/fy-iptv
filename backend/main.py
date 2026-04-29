# FY-IPTV 应用入口
#
# 路由挂载：
#   /api/user/*    - 用户注册、登录、个人信息
#   /api/orders/*  - 套餐列表、创建订单、支付回调、订单历史
#   /api/admin/*   - 管理后台（需管理员权限）
#   /m3u           - M3U 订阅代理（token 鉴权）
#   /              - 前端静态文件（index.html / dashboard.html / admin.html）
#
# 启动时若数据库中不存在管理员账号，自动创建 admin/admin123，请立即修改

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal
import models, auth, os, secrets

Base.metadata.create_all(bind=engine)

app = FastAPI(title="FY-IPTV", docs_url=None, redoc_url=None)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from routers import user, orders, admin, m3u
app.include_router(user.router,   prefix="/api/user")
app.include_router(orders.router, prefix="/api/orders")
app.include_router(admin.router,  prefix="/api/admin")
app.include_router(m3u.router)

frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.on_event("startup")
def init_admin():
    db = SessionLocal()
    try:
        if not db.query(models.User).filter_by(is_admin=True).first():
            db.add(models.User(
                username="admin",
                password_hash=auth.hash_password("admin123"),
                m3u_token=secrets.token_hex(24),
                is_admin=True,
                is_active=True,
            ))
            db.commit()
            print("✅ 默认管理员已创建：admin / admin123，请立即修改密码")
    finally:
        db.close()
