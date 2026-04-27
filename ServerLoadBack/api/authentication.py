from dataclasses import dataclass
from typing import Optional

from rest_framework import authentication
from rest_framework import exceptions

from .models import Server


@dataclass
class AgentUser:
    server: Server

    @property
    def is_authenticated(self) -> bool:
        return True


class AgentTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Agent"

    def authenticate(self, request) -> Optional[tuple]:
        auth_header = authentication.get_authorization_header(request).decode("utf-8")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None

        token = parts[1].strip()
        if not token:
            raise exceptions.AuthenticationFailed("Missing agent token.")

        try:
            server = Server.objects.get(agent_token=token)
        except Server.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("Invalid agent token.") from exc

        server.touch_last_seen()
        return AgentUser(server=server), server
