from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    base_dir = BASE_DIR
    secret_key = os.getenv('HAYAVEGA_SECRET_KEY', 'change-this-in-production')
    debug = os.getenv('HAYAVEGA_DEBUG', 'true').lower() == 'true'
    allowed_hosts = ['127.0.0.1', 'localhost']

    installed_apps = ['employees']
    middleware = []
    root_urlconf = 'config.routes'

    class database:
        engine = 'sqlite3'
        name = BASE_DIR / 'hayavega.sqlite3'

    class server:
        host = '127.0.0.1'
        port = 8000
        engine = 'rust'  # manage.py launch's default (wsgiref) is documented dev-only; a real/load-test server needs this or gunicorn/waitress
        workers = 16

    class security:
        # 120 req/60s per client IP is Hayavega's hardened-by-default
        # value -- correct for a single end user, but a real HRMS behind
        # a corporate NAT/VPN can have thousands of employees sharing one
        # apparent IP. Tuned here for this app's actual expected traffic
        # shape, not disabled -- see FINDINGS.md.
        rate_limit = 6000
        rate_window_seconds = 60


settings = Settings()
