"""Verification helpers for the optional Google Identity Services login."""
import os


def authoritative_identity(claims):
    email = claims.get('email')
    sub = claims.get('sub')
    if not isinstance(email, str) or not isinstance(sub, str) or not sub or claims.get('email_verified') is not True:
        raise ValueError('Unverified Google identity')
    email = email.strip().lower()
    if email.count('@') != 1:
        raise ValueError('Invalid email')
    domain = email.rsplit('@', 1)[1]
    hd = claims.get('hd')
    if domain != 'gmail.com' and not (isinstance(hd, str) and hd.lower() == domain):
        raise PermissionError('Manual account verification required')
    return sub, email


def verify_google_id_token(token, client_id):
    from google.auth import exceptions
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token
    try:
        claims = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
    except exceptions.TransportError as exc:
        raise RuntimeError('Google verification unavailable') from exc
    except exceptions.GoogleAuthError as exc:
        raise ValueError('Invalid Google token') from exc
    if claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        raise ValueError('Invalid issuer')
    authoritative_identity(claims)
    return claims


def allowed_origin(origin):
    allowed = {v.strip().rstrip('/') for v in os.environ.get('GOOGLE_AUTH_ALLOWED_ORIGINS', '').split(',') if v.strip()}
    return bool(origin and origin in allowed)
