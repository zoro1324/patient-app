# myapp/asgi.py (inside the inner myapp directory)

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import zego_app.routing # Assuming 'zego_app' is the name of your Django app for Zego logic

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings') # <--- Ensure 'myapp.settings' here too

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            zego_app.routing.websocket_urlpatterns
        )
    ),
})