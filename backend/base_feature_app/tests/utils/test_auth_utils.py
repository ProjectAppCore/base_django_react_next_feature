"""Verify authentication token payloads and email-delivery outcomes."""

import logging
import smtplib

import pytest
from django.contrib.auth import get_user_model

from base_feature_app.utils import auth_utils


@pytest.mark.django_db
def test_generate_auth_tokens_contains_user_payload():
    """Generated authentication tokens include the authenticated user's data."""
    User = get_user_model()
    user = User.objects.create_user(email='tokens@example.com', password='pass1234')

    tokens = auth_utils.generate_auth_tokens(user)

    assert tokens['user']['email'] == 'tokens@example.com'
    assert tokens['user']['id'] == user.id
    assert tokens['refresh']
    assert tokens['access']


@pytest.mark.django_db
def test_send_password_reset_code_success(monkeypatch):
    """Successful password-reset email delivery returns success."""
    User = get_user_model()
    user = User.objects.create_user(email='reset@example.com', password='pass1234', first_name='Reset')
    sent = {}

    def fake_send_mail(subject, message, from_email, recipient_list, fail_silently):
        sent['subject'] = subject
        sent['recipients'] = recipient_list
        return 1

    monkeypatch.setattr(auth_utils, 'send_mail', fake_send_mail)

    assert auth_utils.send_password_reset_code(user, '123456') is True
    assert sent['recipients'] == [user.email]


@pytest.mark.django_db
def test_send_password_reset_code_failure(monkeypatch):
    """Failed password-reset email delivery returns failure."""
    User = get_user_model()
    user = User.objects.create_user(email='resetfail@example.com', password='pass1234', first_name='Reset')

    def fake_send_mail(*_args, **_kwargs):
        raise RuntimeError('send failed')

    monkeypatch.setattr(auth_utils, 'send_mail', fake_send_mail)

    assert auth_utils.send_password_reset_code(user, '123456') is False


@pytest.mark.django_db
def test_send_verification_code_success(monkeypatch):
    """Successful verification email delivery returns success."""
    sent = {}

    def fake_send_mail(subject, message, from_email, recipient_list, fail_silently):
        sent['subject'] = subject
        sent['recipients'] = recipient_list
        return 1

    monkeypatch.setattr(auth_utils, 'send_mail', fake_send_mail)

    assert auth_utils.send_verification_code('verify@example.com', '654321') is True
    assert sent['recipients'] == ['verify@example.com']


@pytest.mark.django_db
def test_send_verification_code_failure(monkeypatch):
    """Failed verification email delivery returns failure."""
    def fake_send_mail(*_args, **_kwargs):
        raise RuntimeError('send failed')

    monkeypatch.setattr(auth_utils, 'send_mail', fake_send_mail)

    assert auth_utils.send_verification_code('verify@example.com', '654321') is False


@pytest.mark.django_db
@pytest.mark.parametrize(('function_name', 'event'), [
    ('send_password_reset_code', 'Password reset email failed'),
    ('send_verification_code', 'Verification email failed'),
])
def test_email_failure_diagnostic_is_sanitized(function_name, event, monkeypatch, caplog, capsys):
    """Mail transport failures record their type without printing sensitive text."""
    user = get_user_model().objects.create_user(email='sensitive@example.com', password='pass1234')
    sentinel = 'SENSITIVE_RECOVERY_TOKEN'
    arguments = {
        'send_password_reset_code': (user, sentinel),
        'send_verification_code': (user.email, sentinel),
    }
    caplog.set_level(logging.ERROR, logger=auth_utils.__name__)

    def fail_send(*_args, **_kwargs):
        raise smtplib.SMTPRecipientsRefused({user.email: (550, sentinel.encode())})

    monkeypatch.setattr(auth_utils, 'send_mail', fail_send)
    result = getattr(auth_utils, function_name)(*arguments[function_name])

    assert result is False
    assert f'{event}: error_type=SMTPRecipientsRefused' in caplog.text
    assert user.email not in caplog.text
    assert sentinel not in caplog.text
    assert 'Traceback' not in caplog.text
    assert capsys.readouterr().out == ''
