from django.http import HttpResponseForbidden
import os

ALLOWED_IFRAME_ORIGINS = [
    "https://solwindenergy.com",
    "https://jafaenergy.com",
]

# Optional: Add local dev origins + your PythonAnywhere domain
ALLOWED_DEV_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://mirzajonov.pythonanywhere.com"
]

class AllowOnlyMySitesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        referer = request.META.get('HTTP_REFERER', '')
        origin = request.META.get('HTTP_ORIGIN', '')

        # Allow all if environment variable is set (for local/dev)
        if os.getenv("DJANGO_ALLOW_ALL", "false") == "true":
            return self.get_response(request)

        allowed_origins = ALLOWED_IFRAME_ORIGINS + ALLOWED_DEV_ORIGINS

        # Check referer header
        if referer and not any(referer.startswith(site) for site in allowed_origins):
            return HttpResponseForbidden("Access Denied: Invalid Referer")

        # Check origin header
        if origin and not any(origin.startswith(site) for site in allowed_origins):
            return HttpResponseForbidden("Access Denied: Invalid Origin")

        return self.get_response(request)


class CSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "frame-ancestors https://solwindenergy.com https://jafaenergy.com "
            "http://localhost:8000 http://127.0.0.1:8000 https://mirzajonov.pythonanywhere.com"
        )
        return response
