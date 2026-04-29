# FY-IPTV

IPTV 订阅管理平台，支持用户注册、套餐购买、直播源鉴权与设备并发控制。

## 功能

- **用户系统**：注册（开放/邀请码）、登录、个人中心
- **订阅管理**：套餐购买、自动续期、有效期展示
- **M3U 鉴权**：按 token 访问，校验有效期 + 设备并发数 + 请求频率
- **设备限制**：10分钟时间窗口内活跃 IP 数不超过上限，防中转滥用
- **支付对接**：彩虹易支付（RSA-SHA256 签名，支持支付宝/微信/QQ/云闪付）
- **管理后台**：用户管理、套餐配置、邀请码生成、订单查看、数据统计

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11 · FastAPI · SQLAlchemy · SQLite |
| 前端 | Tailwind CSS · Alpine.js（无构建步骤） |
| 部署 | systemd · Caddy |

## 目录结构

```
fy-iptv/
├── backend/
│   ├── main.py              # 应用入口，路由挂载，管理员初始化
│   ├── models.py            # 数据库模型
│   ├── auth.py              # JWT 鉴权，密码工具
│   ├── payment.py           # 彩虹易支付客户端
│   ├── config.py            # 读取 config.json
│   ├── database.py          # SQLAlchemy 初始化
│   └── routers/
│       ├── user.py          # 注册、登录、个人信息
│       ├── orders.py        # 套餐、创建订单、支付回调
│       ├── admin.py         # 管理后台接口
│       └── m3u.py           # M3U 订阅代理（鉴权核心）
├── frontend/
│   ├── index.html           # 首页 / 登录 / 注册
│   ├── dashboard.html       # 用户中心
│   └── admin.html           # 管理后台
├── config.example.json      # 配置模板
└── requirements.txt
```

## 快速部署

### 1. 克隆项目

```bash
git clone https://github.com/Laiqingde/fy-iptv.git
cd fy-iptv
```

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install "bcrypt==4.0.1"   # 兼容 passlib
```

### 3. 配置

```bash
cp config.example.json config.json
```

编辑 `config.json`：

```json
{
  "app": {
    "secret_key": "替换为随机字符串",
    "base_url": "http://你的服务器IP:8091",
    "title": "FY-IPTV"
  },
  "registration": {
    "mode": "open"
  },
  "payment": {
    "apiurl": "https://你的支付平台地址/",
    "pid": "商户ID",
    "platform_public_key": "平台公钥",
    "merchant_private_key": "商户私钥"
  }
}
```

`registration.mode` 可选值：
- `"open"` — 开放注册
- `"invite"` — 仅限邀请码注册

### 4. 启动

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8091
```

首次启动自动创建管理员账号 `admin / admin123`，**请立即登录后台修改密码**。

### 5. systemd 服务（生产环境）

```ini
[Unit]
Description=FY-IPTV Service
After=network.target

[Service]
WorkingDirectory=/opt/fy-iptv/backend
ExecStart=/opt/fy-iptv/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8091 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```

## 访问地址

| 页面 | 地址 |
|---|---|
| 首页 / 登录 | `http://服务器IP:8091` |
| 用户中心 | `http://服务器IP:8091/dashboard.html` |
| 管理后台 | `http://服务器IP:8091/admin.html` |
| M3U 订阅 | `http://服务器IP:8091/m3u?token=用户token` |

## M3U 文件配置

本项目读取 `/var/www/m3u/playlist.m3u` 作为直播源，需配合自动更新脚本使用。

如需定时从远程拉取并过滤失效源，可参考 [m3u_updater.py](https://gist.github.com/) 的实现思路：定时拉取 → 并发检测可用性 → 写入上述路径。

## 防滥用机制

| 机制 | 规则 |
|---|---|
| 设备并发限制 | 10分钟窗口内活跃 IP 数 ≤ `max_devices`（默认2） |
| 请求频率限制 | 同一 token 每小时请求超过50次自动封号 |
| 设备数可调 | 管理员可对每个用户单独调整设备上限 |

## 支付对接

使用彩虹易支付，签名算法：RSA-SHA256（PKCS1v15）。

回调地址：`http://服务器IP:8091/api/orders/notify`（需在支付平台后台配置）

## License

MIT
