import json, os

_cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')

def load():
    with open(_cfg_path, 'r', encoding='utf-8') as f:
        return json.load(f)

cfg = load()
APP = cfg['app']
PAYMENT = cfg['payment']
REGISTRATION = cfg['registration']
