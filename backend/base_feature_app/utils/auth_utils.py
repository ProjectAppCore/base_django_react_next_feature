"""
Authentication utility functions.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)


def generate_auth_tokens(user):
    """
    Generate JWT tokens for a user.
    
    :param user: User instance
    :return: Dictionary with refresh, access tokens and user data
    """
    refresh = RefreshToken.for_user(user)
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_staff': user.is_staff,
        }
    }


def send_password_reset_code(user, code):
    """
    Send password reset code via email.
    
    :param user: User instance
    :param code: complete password-reset token
    """
    subject = 'Password Reset Code'
    message = f'''
Hello {user.first_name},

You requested a password reset. Your verification code is:

{code}

This code will expire in 15 minutes.

If you didn't request this, please ignore this email.

Best regards,
The Team
    '''
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception as exc:  # noqa: BLE001 -- Preserve the generic boundary without exposing exception text.
        logger.error('Password reset email failed: error_type=%s', type(exc).__name__)
        return False


def send_verification_code(email, code):
    """
    Send verification code for new user registration.
    
    :param email: User email
    :param code: 6-digit code
    """
    subject = 'Email Verification Code'
    message = f'''
Hello,

Welcome! Your email verification code is:

{code}

This code will expire in 15 minutes.

Best regards,
The Team
    '''
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return True
    except Exception as exc:  # noqa: BLE001 -- Preserve the generic boundary without exposing exception text.
        logger.error('Verification email failed: error_type=%s', type(exc).__name__)
        return False
