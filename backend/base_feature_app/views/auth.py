"""
Authentication views for user sign up, sign in, and password management.
"""
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth import get_user_model
from django.conf import settings

import requests

from base_feature_app.models import PasswordCode
from base_feature_app.utils.auth_utils import (
    generate_auth_tokens, 
    send_password_reset_code,
    send_verification_code
)
from base_feature_app.views.captcha_views import verify_recaptcha

User = get_user_model()

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def sign_up(request):
    """
    User registration endpoint.
    
    Expected data:
    - email: str
    - password: str
    - first_name: str (optional)
    - last_name: str (optional)
    """
    captcha_token = request.data.get('captcha_token', '')
    if not verify_recaptcha(captcha_token):
        return Response(
            {'captcha_token': ['reCAPTCHA verification failed.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password')
    first_name = request.data.get('first_name', '').strip()
    last_name = request.data.get('last_name', '').strip()
    
    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(password) < 8:
        return Response(
            {'error': 'Password must be at least 8 characters'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'User with this email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create user
    user = User.objects.create(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=make_password(password),
        is_active=True
    )
    
    # Generate tokens
    tokens = generate_auth_tokens(user)
    
    return Response(tokens, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def sign_in(request):
    """
    User sign in endpoint.
    
    Expected data:
    - email: str
    - password: str
    """
    captcha_token = request.data.get('captcha_token', '')
    if not verify_recaptcha(captcha_token):
        return Response(
            {'captcha_token': ['reCAPTCHA verification failed.']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password')
    
    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    if not check_password(password, user.password):
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    if not user.is_active:
        return Response(
            {'error': 'Account is inactive'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Generate tokens
    tokens = generate_auth_tokens(user)
    
    return Response(tokens, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def google_login(request):
    """
    Google OAuth login endpoint.
    
    Expected data:
    - email: str
    - given_name: str (optional)
    - family_name: str (optional)
    - picture: str (optional)
    """
    credential = request.data.get('credential') or request.data.get('id_token')

    if not credential:
        return Response({'error': 'Google credential is required'}, status=status.HTTP_400_BAD_REQUEST)

    email = request.data.get('email', '').strip().lower()
    given_name = request.data.get('given_name', '').strip()
    family_name = request.data.get('family_name', '').strip()
    picture_url = request.data.get('picture', '')

    payload = None
    aud_mismatch = False
    try:
        tokeninfo = requests.get(
            'https://oauth2.googleapis.com/tokeninfo',
            params={'id_token': credential},
            timeout=5,
        )
        if tokeninfo.status_code == 200:
            payload = tokeninfo.json()
        else:
            logger.warning('Google tokeninfo rejected credential: status=%s', tokeninfo.status_code)
    except (requests.RequestException, ValueError) as exc:
        logger.warning('Google token validation failed: error_type=%s', type(exc).__name__)

    if payload is not None:
        aud = payload.get('aud', '')
        allowed_auds = [v.strip() for v in (settings.GOOGLE_OAUTH_CLIENT_ID or '').split(',') if v.strip()]
        if allowed_auds and aud not in allowed_auds:
            logger.warning('Google aud mismatch. aud=%s allowed=%s', aud, allowed_auds)
            aud_mismatch = True
            payload = None

    if payload is None and not settings.DEBUG:
        if aud_mismatch:
            return Response({'error': 'Invalid Google client'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({'error': 'Invalid Google credential'}, status=status.HTTP_401_UNAUTHORIZED)

    if payload is not None:
        token_email = (payload.get('email') or '').strip().lower()
        if token_email:
            email = token_email

        token_given = (payload.get('given_name') or '').strip()
        token_family = (payload.get('family_name') or '').strip()
        token_picture = payload.get('picture') or ''

        if token_given:
            given_name = token_given
        if token_family:
            family_name = token_family
        if token_picture:
            picture_url = token_picture
    
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get or create user
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'first_name': given_name,
            'last_name': family_name,
            'is_active': True,
        }
    )

    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    
    # Update names if user exists but doesn't have them
    if not created:
        if not user.first_name and given_name:
            user.first_name = given_name
        if not user.last_name and family_name:
            user.last_name = family_name
        if user.first_name or user.last_name:
            user.save()
    
    # Generate tokens
    tokens = generate_auth_tokens(user)
    tokens['created'] = created
    tokens['google_validated'] = payload is not None
    
    return Response(tokens, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def send_passcode(request):
    """
    Send password reset code to user's email.
    
    Expected data:
    - email: str
    """
    email = request.data.get('email', '').strip().lower()
    
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Don't reveal if user exists
        return Response(
            {'message': 'If the email exists, a code has been sent'},
            status=status.HTTP_200_OK
        )
    
    # Generate and save code
    password_code = PasswordCode.generate_code(user)
    
    # Send email
    success = send_password_reset_code(user, password_code.code)
    
    if not success:
        return Response(
            {'error': 'Failed to send email'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return Response(
        {'message': 'Code sent successfully'},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_passcode_and_reset_password(request):
    """
    Verify passcode and reset password.
    
    Expected data:
    - email: str
    - code: str
    - new_password: str
    """
    email = request.data.get('email', '').strip().lower()
    code = request.data.get('code', '').strip()
    new_password = request.data.get('new_password')
    
    if not email or not code or not new_password:
        return Response(
            {'error': 'Email, code, and new password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid email or code'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Find valid code
    try:
        password_code = user.password_codes.filter(
            code=code,
            used=False
        ).first()
        
        if not password_code or not password_code.is_valid():
            return Response(
                {'error': 'Invalid or expired code'},
                status=status.HTTP_400_BAD_REQUEST
            )
    except Exception:
        return Response(
            {'error': 'Invalid or expired code'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not isinstance(new_password, str) or len(new_password) < 8:
        return Response(
            {'error': 'Password must be at least 8 characters'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Update password
    user.password = make_password(new_password)
    user.save()
    
    # Mark code as used
    password_code.used = True
    password_code.save()
    
    return Response(
        {'message': 'Password reset successfully'},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_password(request):
    """
    Update user password (requires authentication).
    
    Expected data:
    - current_password: str
    - new_password: str
    """
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    
    if not current_password or not new_password:
        return Response(
            {'error': 'Current password and new password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = request.user
    
    if not check_password(current_password, user.password):
        return Response(
            {'error': 'Current password is incorrect'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not isinstance(new_password, str) or len(new_password) < 8:
        return Response(
            {'error': 'Password must be at least 8 characters'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.password = make_password(new_password)
    user.save()
    
    return Response(
        {'message': 'Password updated successfully'},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validate_token(request):
    """
    Validate JWT token and return user info.
    """
    user = request.user
    return Response({
        'valid': True,
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_staff': user.is_staff,
        }
    }, status=status.HTTP_200_OK)
