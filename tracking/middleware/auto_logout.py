from django.conf import settings
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.utils import timezone

class AutoLogoutMiddleware:
    """
    Logs out a user automatically when session expires
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            session_key = request.session.session_key
            if session_key:
                try:
                    session = Session.objects.get(session_key=session_key)
                    if session.expire_date < timezone.now():
                        logout(request)
                except Session.DoesNotExist:
                    logout(request)
        response = self.get_response(request)
        return response
