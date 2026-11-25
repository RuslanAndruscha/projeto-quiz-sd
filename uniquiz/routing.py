from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r'^ws/competitivo/partida/(?P<partida_id>\d+)/$',
        consumers.Partida1v1Consumer.as_asgi(),
    ),
]