# utils.py (app folder mein)

from django.conf import settings

def set_auth_cookies(response, access_token=None, refresh_token=None):
    """
    Response mein JWT cookies set karo
    """
    if access_token:
        response.set_cookie(
            key=settings.JWT_AUTH_COOKIE,
            value=access_token,
            max_age=settings.JWT_AUTH_COOKIE_MAX_AGE,
            httponly=settings.COOKIE_HTTPONLY,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            path=settings.COOKIE_PATH,
            domain=settings.COOKIE_DOMAIN,
        )
    
    if refresh_token:
        response.set_cookie(
            key=settings.JWT_REFRESH_COOKIE,
            value=refresh_token,
            max_age=settings.JWT_REFRESH_COOKIE_MAX_AGE,
            httponly=settings.COOKIE_HTTPONLY,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            path=settings.COOKIE_PATH,
            domain=settings.COOKIE_DOMAIN,
        )
    
    return response


def clear_auth_cookies(response):
    """
    Cookies delete karo (logout ke liye)
    """
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
    return response