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

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


@app.on_event("startup")
def init_admin():
    db = SessionLocal()
    try:
        if not db.query(models.User).filter_by(is_admin=True).first():
            admin_user = models.User(
                username="admin",
                password_hash=auth.hash_password("admin123"),
                m3u_token=secrets.token_hex(24),
                is_admin=True,
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            print("✅ 默认管理员已创建：admin / admin123，请立即修改密码")
    finally:
        db.close()
