import base64, time, urllib.parse
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import httpx, config

_cfg = config.PAYMENT


def _get_sign_content(params: dict) -> str:
    filtered = {k: v for k, v in params.items()
                if k not in ('sign', 'sign_type') and v is not None and str(v).strip() != ''}
    sorted_items = sorted(filtered.items())
    return '&'.join(f"{k}={v}" for k, v in sorted_items)


def _sign(data: str) -> str:
    key_pem = (
        "-----BEGIN PRIVATE KEY-----\n"
        + '\n'.join(_cfg['merchant_private_key'][i:i+64] for i in range(0, len(_cfg['merchant_private_key']), 64))
        + "\n-----END PRIVATE KEY-----"
    )
    private_key = serialization.load_pem_private_key(key_pem.encode(), password=None, backend=default_backend())
    sig = private_key.sign(data.encode('utf-8'), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


def verify_callback(params: dict) -> bool:
    if not params.get('sign'):
        return False
    ts = params.get('timestamp', 0)
    if abs(time.time() - int(ts)) > 300:
        return False
    key_pem = (
        "-----BEGIN PUBLIC KEY-----\n"
        + '\n'.join(_cfg['platform_public_key'][i:i+64] for i in range(0, len(_cfg['platform_public_key']), 64))
        + "\n-----END PUBLIC KEY-----"
    )
    public_key = serialization.load_pem_public_key(key_pem.encode(), backend=default_backend())
    try:
        public_key.verify(
            base64.b64decode(params['sign']),
            _get_sign_content(params).encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False


def build_pay_params(out_trade_no: str, name: str, money: float,
                     notify_url: str, return_url: str, pay_type: str) -> dict:
    params = {
        'pid': _cfg['pid'],
        'type': pay_type,
        'out_trade_no': out_trade_no,
        'notify_url': notify_url,
        'return_url': return_url,
        'name': name,
        'money': f"{money:.2f}",
        'timestamp': str(int(time.time())),
    }
    params['sign'] = _sign(_get_sign_content(params))
    params['sign_type'] = 'RSA'
    return params


def get_pay_url(out_trade_no: str, name: str, money: float,
                notify_url: str, return_url: str, pay_type: str) -> str:
    params = build_pay_params(out_trade_no, name, money, notify_url, return_url, pay_type)
    return _cfg['apiurl'].rstrip('/') + '/api/pay/submit?' + urllib.parse.urlencode(params)


async def query_order(trade_no: str) -> dict:
    params = {
        'pid': _cfg['pid'],
        'trade_no': trade_no,
        'timestamp': str(int(time.time())),
    }
    params['sign'] = _sign(_get_sign_content(params))
    params['sign_type'] = 'RSA'
    async with httpx.AsyncClient(verify=False, timeout=10) as client:
        r = await client.post(_cfg['apiurl'].rstrip('/') + '/api/pay/query', data=params)
        return r.json()
