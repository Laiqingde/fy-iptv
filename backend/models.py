# 数据库模型
#
# User        - 用户账号，含订阅到期时间、M3U token、设备上限
# Plan        - 订阅套餐（名称、价格、有效天数）
# Order       - 支付订单，status: 0=待支付 1=已支付 2=已失效
# InviteCode  - 邀请码，支持限制使用次数
# DeviceLog   - 设备访问记录，用于并发设备数统计（按 IP 去重）

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    m3u_token = Column(String(64), unique=True, index=True, nullable=False)
    expired_at = Column(DateTime, nullable=True)
    max_devices = Column(Integer, default=2)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    invite_code_used = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("Order", back_populates="user")
    device_logs = relationship("DeviceLog", back_populates="user", cascade="all, delete-orphan")


class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    description = Column(String(256), nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=True)
    out_trade_no = Column(String(64), unique=True, index=True, nullable=False)
    trade_no = Column(String(64), nullable=True)
    amount = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    status = Column(Integer, default=0)  # 0=待支付 1=已支付 2=已失效
    payment_type = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="orders")
    plan = relationship("Plan")


class InviteCode(Base):
    __tablename__ = "invite_codes"
    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, index=True, nullable=False)
    max_uses = Column(Integer, default=1)
    use_count = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    note = Column(String(128), nullable=True)


class DeviceLog(Base):
    __tablename__ = "device_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    ip = Column(String(64), nullable=False)
    user_agent = Column(String(256), nullable=True)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="device_logs")
