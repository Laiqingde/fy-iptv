from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
import models, auth, payment, config
from datetime import datetime
import secrets

router = APIRouter(tags=["订单"])


class CreateOrderIn(BaseModel):
    plan_id: int
    pay_type: str = "alipay"


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    plans = db.query(models.Plan).filter_by(is_active=True).order_by(models.Plan.sort_order).all()
    return [{"id": p.id, "name": p.name, "price": p.price,
             "duration_days": p.duration_days, "description": p.description} for p in plans]


@router.post("/create")
def create_order(body: CreateOrderIn, request: Request,
                 user: models.User = Depends(auth.get_current_user),
                 db: Session = Depends(get_db)):
    plan = db.query(models.Plan).filter_by(id=body.plan_id, is_active=True).first()
    if not plan:
        raise HTTPException(404, "套餐不存在")
    if body.pay_type not in ('alipay', 'wxpay', 'qqpay', 'bank'):
        raise HTTPException(400, "不支持的支付方式")

    out_trade_no = f"FY{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(4).upper()}"
    base = config.APP['base_url']
    notify_url = f"{base}/api/orders/notify"
    return_url = f"{base}/dashboard.html"

    order = models.Order(
        user_id=user.id,
        plan_id=plan.id,
        out_trade_no=out_trade_no,
        amount=plan.price,
        duration_days=plan.duration_days,
        payment_type=body.pay_type,
    )
    db.add(order)
    db.commit()

    pay_url = payment.get_pay_url(
        out_trade_no=out_trade_no,
        name=f"{config.APP['title']} - {plan.name}",
        money=plan.price,
        notify_url=notify_url,
        return_url=return_url,
        pay_type=body.pay_type,
    )
    return {"pay_url": pay_url, "out_trade_no": out_trade_no}


@router.get("/notify")
def payment_notify(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    if not payment.verify_callback(params):
        return "fail"

    if params.get('trade_status') != 'TRADE_SUCCESS':
        return "success"

    out_trade_no = params.get('out_trade_no')
    order = db.query(models.Order).filter_by(out_trade_no=out_trade_no).first()
    if not order or order.status == 1:
        return "success"

    order.status = 1
    order.trade_no = params.get('trade_no')
    order.paid_at = datetime.utcnow()

    user = db.query(models.User).filter_by(id=order.user_id).first()
    if user:
        now = datetime.utcnow()
        base = user.expired_at if user.expired_at and user.expired_at > now else now
        from datetime import timedelta
        user.expired_at = base + timedelta(days=order.duration_days)

    db.commit()
    return "success"


@router.get("/my")
def my_orders(user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    orders = db.query(models.Order).filter_by(user_id=user.id).order_by(models.Order.created_at.desc()).limit(20).all()
    return [{"out_trade_no": o.out_trade_no, "amount": o.amount, "duration_days": o.duration_days,
             "status": o.status, "payment_type": o.payment_type,
             "created_at": o.created_at.isoformat(),
             "paid_at": o.paid_at.isoformat() if o.paid_at else None} for o in orders]
