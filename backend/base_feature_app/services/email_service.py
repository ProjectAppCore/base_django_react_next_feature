"""
Email service for handling all outbound email notifications.

Centralizes email logic following the service layer pattern.
Delegates to utility functions that wrap Django's send_mail.
"""
from base_feature_app.utils.auth_utils import (
    send_password_reset_code,
    send_verification_code,
)


class EmailService:
    """
    Service class for sending email notifications.

    Provides static methods for all transactional emails sent
    by the application, abstracting the underlying mail backend.
    """

    @staticmethod
    def send_password_reset_code(user, code: str) -> bool:
        """
        Send a password reset verification code to the user.

        Args:
            user: User instance with email and first_name attributes.
            code: Complete password-reset token.

        Returns:
            bool: True if the email was sent successfully, False otherwise.
        """
        return send_password_reset_code(user, code)

    @staticmethod
    def send_verification_code(email: str, code: str) -> bool:
        """
        Send an email verification code to a new user.

        Args:
            email: Recipient email address.
            code: 6-digit alphanumeric verification code.

        Returns:
            bool: True if the email was sent successfully, False otherwise.
        """
        return send_verification_code(email, code)
