from rest_framework.permissions import BasePermission

from .models import Server


class IsAgentAuthenticated(BasePermission):
    def has_permission(self, request, view) -> bool:
        
        return isinstance(request.auth, Server)
