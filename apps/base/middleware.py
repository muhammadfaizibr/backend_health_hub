# middleware.py

from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import json

class JWTAuthFromCookieMiddleware(MiddlewareMixin):
    """
    Cookie se JWT token extract karke Authorization header mein add karo
    """
    def process_request(self, request):
        access_token = request.COOKIES.get(settings.JWT_AUTH_COOKIE)
        
        if access_token and not request.META.get('HTTP_AUTHORIZATION'):
            request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
        
        return None


class JWTCookieResponseMiddleware(MiddlewareMixin):
    """
    🔥 MAGIC: Automatically response mein tokens detect karke cookies set karo
    Views.py mein KUCH NAHI karna padega!
    """
    
    def process_response(self, request, response):
        # Check if response has data attribute (DRF Response)
        if not hasattr(response, 'data'):
            return response
        
        # Check if data is dict
        if not isinstance(response.data, dict):
            return response
        
        # Extract tokens from response data
        access_token = None
        refresh_token = None
        
        # Check different possible key names
        if 'access' in response.data:
            access_token = response.data.get('access')
        elif 'access_token' in response.data:
            access_token = response.data.get('access_token')
        
        if 'refresh' in response.data:
            refresh_token = response.data.get('refresh')
        elif 'refresh_token' in response.data:
            refresh_token = response.data.get('refresh_token')
        
        # Set cookies if tokens found
        if access_token:
            self._set_access_cookie(response, access_token)
            # Response body se remove karo (security)
            response.data.pop('access', None)
            response.data.pop('access_token', None)
        
        if refresh_token:
            self._set_refresh_cookie(response, refresh_token)
            # Response body se remove karo
            response.data.pop('refresh', None)
            response.data.pop('refresh_token', None)
        
        # Check for logout action (cookies clear karo)
        if request.path.endswith('/logout/') and response.status_code == 200:
            self._clear_cookies(response)
        
        return response
    
    def _set_access_cookie(self, response, token):
        """Set access token cookie"""
        response.set_cookie(
            key=settings.JWT_AUTH_COOKIE,
            value=token,
            max_age=settings.JWT_AUTH_COOKIE_MAX_AGE,
            httponly=settings.COOKIE_HTTPONLY,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            path=settings.COOKIE_PATH,
            domain=settings.COOKIE_DOMAIN,
        )
    
    def _set_refresh_cookie(self, response, token):
        """Set refresh token cookie"""
        response.set_cookie(
            key=settings.JWT_REFRESH_COOKIE,
            value=token,
            max_age=settings.JWT_REFRESH_COOKIE_MAX_AGE,
            httponly=settings.COOKIE_HTTPONLY,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            path=settings.COOKIE_PATH,
            domain=settings.COOKIE_DOMAIN,
        )
    
    def _clear_cookies(self, response):
        """Clear auth cookies"""
        response.delete_cookie(
            key=settings.JWT_AUTH_COOKIE,
            path=settings.COOKIE_PATH,
            domain=settings.COOKIE_DOMAIN,
        )
        response.delete_cookie(
            key=settings.JWT_REFRESH_COOKIE,
            path=settings.COOKIE_PATH,
            domain=settings.COOKIE_DOMAIN,
        )