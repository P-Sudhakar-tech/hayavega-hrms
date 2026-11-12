"""ASGI entry point -- opt in only if a view needs `async def` for
concurrent I/O; the WSGI path above (`config/wsgi.py`) remains the
default and does not require this file. Point an ASGI server at the
`application` object below. For example:

    uvicorn config.asgi:application --workers 4 --host 0.0.0.0 --port 8000
    hypercorn config.asgi:application --workers 4 --bind 0.0.0.0:8000

See DEPLOYMENT.md for when ASGI is worth the switch and when it isn't.
"""
from hayavega.asgi import create_asgi_application
from hayavega.conf import load_settings
from hayavega.hardening import HardeningOptions
from hayavega.middleware import load_middleware

settings = load_settings('config.settings')
urls = __import__(settings.root_urlconf, fromlist=['urlpatterns'])

application = create_asgi_application(
    urls.urlpatterns,
    hardening=HardeningOptions.from_settings(allowed_hosts=settings.allowed_hosts, security=settings.security),
    debug=settings.debug,
    middleware=load_middleware(settings.middleware),
)
