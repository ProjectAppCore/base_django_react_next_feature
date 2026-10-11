"""Verify authentication and password-recovery endpoint responses."""

import logging
from datetime import timedelta
from unittest.mock import patch

import pytest
import requests
from django.contrib.auth import get_user_model
from django.db import OperationalError, connection
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework import status

from base_feature_app.models import PasswordCode
from base_feature_app.views import auth as auth_views


class DummyResponse:
    """Represent an external HTTP response used by authentication endpoint tests."""

    def __init__(self, status_code=200, payload=None, text=''):
        """Initialize the response status, JSON payload, and text body."""
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        """Return the configured JSON response payload."""
        return self._payload


@pytest.mark.django_db
@patch('base_feature_app.views.auth.verify_recaptcha', return_value=True)
def test_sign_up_requires_email_and_password(mock_captcha, api_client):
    """Sign-up rejects requests missing the required email or password."""
    response = api_client.post(reverse('sign_up'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Email and password are required'


@pytest.mark.django_db
@patch('base_feature_app.views.auth.verify_recaptcha', return_value=True)
def test_sign_up_rejects_existing_email(mock_captcha, api_client):
    """Sign-up rejects an email address already registered to a user."""
    User = get_user_model()
    User.objects.create_user(email='existing@example.com', password='pass1234')

    response = api_client.post(
        reverse('sign_up'),
        {'email': 'existing@example.com', 'password': 'pass1234'},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'User with this email already exists'


@pytest.mark.django_db
@patch('base_feature_app.views.auth.verify_recaptcha', return_value=True)
def test_sign_up_creates_user(mock_captcha, api_client):
    """Verifies sign-up creates a new user record and returns an access token on success."""
    response = api_client.post(
        reverse('sign_up'),
        {
            'email': 'new@example.com',
            'password': 'pass1234',
            'first_name': 'New',
            'last_name': 'User',
        },
        format='json',
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert 'access' in response.json()

    User = get_user_model()
    user = User.objects.get(email='new@example.com')
    assert user.first_name == 'New'


@pytest.mark.django_db
@patch('base_feature_app.views.auth.verify_recaptcha', return_value=True)
def test_sign_in_requires_fields(mock_captcha, api_client):
    """Sign-in rejects requests missing required credentials."""
    response = api_client.post(reverse('sign_in'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Email and password are required'


@pytest.mark.django_db
@patch('base_feature_app.views.auth.verify_recaptcha', return_value=True)
def test_sign_in_rejects_unknown_user(mock_captcha, api_client):
    """Sign-in rejects an unregistered email address."""
    response = api_client.post(
        reverse('sign_in'),
        {'email': 'missing@example.com', 'password': 'pass1234'},
        format='json',
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()['error'] == 'Invalid credentials'


@pytest.mark.django_db
@patch('base_feature_app.views.auth.verify_recaptcha', return_value=True)
def test_sign_in_rejects_invalid_password(mock_captcha, api_client):
    """Sign-in rejects an incorrect password for an existing user."""
    User = get_user_model()
    User.objects.create_user(email='user@example.com', password='pass1234')

    response = api_client.post(
        reverse('sign_in'),
        {'email': 'user@example.com', 'password': 'wrong'},
        format='json',
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@patch('base_feature_app.views.auth.verify_recaptcha', return_value=True)
def test_sign_in_rejects_inactive_user(mock_captcha, api_client):
    """Sign-in rejects an inactive account."""
    User = get_user_model()
    user = User.objects.create_user(email='inactive@example.com', password='pass1234')
    user.is_active = False
    user.save(update_fields=['is_active'])

    response = api_client.post(
        reverse('sign_in'),
        {'email': 'inactive@example.com', 'password': 'pass1234'},
        format='json',
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()['error'] == 'Account is inactive'


@pytest.mark.django_db
@patch('base_feature_app.views.auth.verify_recaptcha', return_value=True)
def test_sign_in_success(mock_captcha, api_client):
    """Valid sign-in credentials return authentication tokens."""
    User = get_user_model()
    User.objects.create_user(email='active@example.com', password='pass1234')

    response = api_client.post(
        reverse('sign_in'),
        {'email': 'active@example.com', 'password': 'pass1234'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert 'access' in response.json()


@pytest.mark.django_db
def test_google_login_requires_credential(api_client):
    """Google login rejects a request without an identity credential."""
    response = api_client.post(reverse('google_login'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Google credential is required'


@pytest.mark.django_db
@override_settings(DEBUG=False, GOOGLE_OAUTH_CLIENT_ID='')
def test_google_login_invalid_credential_when_not_debug(api_client, monkeypatch):
    """Verifies Google login returns 401 when credential is invalid and the app is not in debug mode."""

    def fake_get(*_args, **_kwargs):
        return DummyResponse(status_code=500)

    monkeypatch.setattr(auth_views.requests, 'get', fake_get)

    response = api_client.post(
        reverse('google_login'),
        {'credential': 'bad-token', 'email': 'user@example.com'},
        format='json',
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()['error'] == 'Invalid Google credential'


@pytest.mark.django_db
@override_settings(DEBUG=False, GOOGLE_OAUTH_CLIENT_ID='client-1')
def test_google_login_aud_mismatch_returns_error(api_client, monkeypatch):
    """Verifies Google login returns 401 when the token audience does not match the configured client ID."""

    def fake_get(*_args, **_kwargs):
        return DummyResponse(status_code=200, payload={'aud': 'other'})

    monkeypatch.setattr(auth_views.requests, 'get', fake_get)

    response = api_client.post(
        reverse('google_login'),
        {'credential': 'bad-aud', 'email': 'user@example.com'},
        format='json',
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()['error'] == 'Invalid Google client'


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_google_login_requires_email_when_payload_missing(api_client, monkeypatch):
    """Verifies Google login returns 400 when the Google API call fails and no fallback email is provided."""

    def fake_get(*_args, **_kwargs):
        raise auth_views.requests.RequestException('fail')

    monkeypatch.setattr(auth_views.requests, 'get', fake_get)

    response = api_client.post(
        reverse('google_login'),
        {'credential': 'token'},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Email is required'


@pytest.mark.django_db
@override_settings(DEBUG=False, GOOGLE_OAUTH_CLIENT_ID='client-1')
def test_google_login_creates_user_with_payload(api_client, monkeypatch):
    """Verifies Google login creates a new user when the token payload contains a valid audience and email."""
    payload = {
        'aud': 'client-1',
        'email': 'google@example.com',
        'given_name': 'Google',
        'family_name': 'User',
        'picture': 'pic',
    }

    def fake_get(*_args, **_kwargs):
        return DummyResponse(status_code=200, payload=payload)

    monkeypatch.setattr(auth_views.requests, 'get', fake_get)

    response = api_client.post(
        reverse('google_login'),
        {'credential': 'token', 'email': 'other@example.com'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data['created'] is True
    assert data['google_validated'] is True

    User = get_user_model()
    user = User.objects.get(email='google@example.com')
    assert user.first_name == 'Google'


@pytest.mark.django_db
@override_settings(DEBUG=False, GOOGLE_OAUTH_CLIENT_ID='client-1')
def test_google_login_updates_existing_user_names(api_client, monkeypatch):
    """Verifies Google login updates the first and last name of an existing user when the payload provides new values."""
    User = get_user_model()
    user = User.objects.create_user(email='existing@example.com', password='pass1234')
    user.first_name = ''
    user.last_name = ''
    user.save(update_fields=['first_name', 'last_name'])

    payload = {
        'aud': 'client-1',
        'email': 'existing@example.com',
        'given_name': 'Given',
        'family_name': 'Name',
    }

    def fake_get(*_args, **_kwargs):
        return DummyResponse(status_code=200, payload=payload)

    monkeypatch.setattr(auth_views.requests, 'get', fake_get)

    response = api_client.post(
        reverse('google_login'),
        {'credential': 'token'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['created'] is False

    user.refresh_from_db()
    assert user.first_name == 'Given'
    assert user.last_name == 'Name'


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_google_login_allows_debug_without_payload(api_client, monkeypatch):
    """Verifies Google login succeeds in debug mode using the fallback email when the Google API call fails."""

    def fake_get(*_args, **_kwargs):
        return DummyResponse(status_code=500)

    monkeypatch.setattr(auth_views.requests, 'get', fake_get)

    response = api_client.post(
        reverse('google_login'),
        {'credential': 'token', 'email': 'debug@example.com'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['google_validated'] is False


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_google_login_sanitizes_transport_failure(api_client, monkeypatch, caplog):
    """Transport failures retain a diagnostic without exposing the credential URL."""
    credential = 'SYNTHETIC_TRANSPORT_CREDENTIAL'
    prepared = requests.Request(
        'GET', 'https://oauth2.googleapis.com/tokeninfo', params={'id_token': credential},
    ).prepare()
    failure = requests.ConnectionError(
        f'Max retries exceeded with url: {prepared.url}', request=prepared,
    )
    caplog.set_level(logging.WARNING, logger=auth_views.__name__)

    def fake_get(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(auth_views.requests, 'get', fake_get)
    response = api_client.post(
        reverse('google_login'), {'credential': credential}, format='json',
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()['error'] == 'Invalid Google credential'
    assert 'Google token validation failed: error_type=ConnectionError' in caplog.text
    assert credential not in caplog.text
    assert prepared.url not in caplog.text
    assert 'Max retries exceeded' not in caplog.text
    assert 'Traceback' not in caplog.text


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_google_login_sanitizes_upstream_rejection(api_client, monkeypatch, caplog):
    """Upstream rejection logs only its status instead of the response body."""
    sentinel = 'SYNTHETIC_UPSTREAM_SECRET'
    caplog.set_level(logging.WARNING, logger=auth_views.__name__)

    def fake_get(*_args, **_kwargs):
        return DummyResponse(status_code=400, text=sentinel)

    monkeypatch.setattr(auth_views.requests, 'get', fake_get)
    response = api_client.post(
        reverse('google_login'), {'credential': 'synthetic-token'}, format='json',
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()['error'] == 'Invalid Google credential'
    assert 'Google tokeninfo rejected credential: status=400' in caplog.text
    assert sentinel not in caplog.text


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_google_login_sanitizes_invalid_json(api_client, monkeypatch, caplog):
    """JSON failures preserve the response contract without logging exception text."""
    sentinel = 'SYNTHETIC_JSON_SECRET'
    caplog.set_level(logging.WARNING, logger=auth_views.__name__)

    class InvalidJsonResponse(DummyResponse):
        """HTTP response whose decoder reports an untrusted error message."""

        def json(self):
            """Simulate a JSON parsing failure at the HTTP boundary."""
            raise ValueError(sentinel)

    def fake_get(*_args, **_kwargs):
        return InvalidJsonResponse()

    monkeypatch.setattr(auth_views.requests, 'get', fake_get)
    response = api_client.post(
        reverse('google_login'), {'credential': 'synthetic-token'}, format='json',
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()['error'] == 'Invalid Google credential'
    assert 'Google token validation failed: error_type=ValueError' in caplog.text
    assert sentinel not in caplog.text


@pytest.mark.django_db
def test_send_passcode_requires_email(api_client):
    """Password-code requests require an email address."""
    response = api_client.post(reverse('send_passcode'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Email is required'


@pytest.mark.django_db
def test_send_passcode_returns_generic_message_for_missing_user(api_client):
    """Password-code requests do not disclose whether an account exists."""
    response = api_client.post(
        reverse('send_passcode'),
        {'email': 'missing@example.com'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['message'] == 'If the email exists, a code has been sent'
    assert PasswordCode.objects.count() == 0


@pytest.mark.django_db
def test_send_passcode_success(api_client, monkeypatch):
    """Password-code requests succeed when the email is delivered."""
    User = get_user_model()
    user = User.objects.create_user(email='send@example.com', password='pass1234')

    monkeypatch.setattr(auth_views, 'send_password_reset_code', lambda *_args, **_kwargs: True)

    response = api_client.post(
        reverse('send_passcode'),
        {'email': user.email},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert PasswordCode.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_send_passcode_failure(api_client, monkeypatch):
    """Password-code requests report failed email delivery."""
    User = get_user_model()
    user = User.objects.create_user(email='fail@example.com', password='pass1234')

    monkeypatch.setattr(auth_views, 'send_password_reset_code', lambda *_args, **_kwargs: False)

    response = api_client.post(
        reverse('send_passcode'),
        {'email': user.email},
        format='json',
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()['error'] == 'Failed to send email'
    assert user.password_codes.filter(used=False).count() == 0


@pytest.mark.django_db
def test_verify_passcode_requires_fields(api_client):
    """Password-code verification requires the expected request fields."""
    response = api_client.post(reverse('verify_passcode_reset'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Email, code, and new password are required'


@pytest.mark.django_db
def test_verify_passcode_rejects_invalid_email(api_client):
    """Password-code verification rejects an unknown account email."""
    response = api_client.post(
        reverse('verify_passcode_reset'),
        {'email': 'missing@example.com', 'code': '123456', 'new_password': 'newpass'},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Invalid email or code'


@pytest.mark.django_db
@freeze_time('2026-01-15 10:00:00')
def test_verify_passcode_rejects_expired_code(api_client):
    """Verifies passcode verification returns 400 when the code was created more than 15 minutes ago."""
    User = get_user_model()
    user = User.objects.create_user(email='expired@example.com', password='pass1234')
    password_code = PasswordCode.generate_code(user)
    PasswordCode.objects.filter(id=password_code.id).update(
        created_at=timezone.now() - timedelta(minutes=16)
    )

    response = api_client.post(
        reverse('verify_passcode_reset'),
        {'email': user.email, 'code': password_code.code, 'new_password': 'newpass'},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Invalid or expired code'


@pytest.mark.django_db
def test_verify_passcode_handles_database_failure(api_client):
    """A failed token lookup leaves credentials unchanged with a generic response."""
    user = get_user_model().objects.create_user(email='boom@example.com', password='pass1234')
    password_code = PasswordCode.generate_code(user)
    original_password = user.password

    def fail_lookup(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith('SELECT') and 'base_feature_app_passwordcode' in sql:
            raise OperationalError('synthetic token lookup failure')
        return execute(sql, params, many, context)

    with connection.execute_wrapper(fail_lookup):
        response = api_client.post(reverse('verify_passcode_reset'), {
            'email': user.email, 'code': password_code.code, 'new_password': 'proposed-password',
        }, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Invalid or expired code'
    user.refresh_from_db()
    password_code.refresh_from_db()
    assert user.password == original_password
    assert password_code.used is False


@pytest.mark.django_db
def test_verify_passcode_logs_sanitized_database_failure(api_client, caplog):
    """A failed token lookup logs only its event and exception type."""
    user = get_user_model().objects.create_user(email='boom@example.com', password='pass1234')
    password_code = PasswordCode.generate_code(user)
    sentinel = f'SENSITIVE {user.email} {password_code.code} proposed-password'
    caplog.set_level(logging.ERROR, logger=auth_views.__name__)

    def fail_lookup(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith('SELECT') and 'base_feature_app_passwordcode' in sql:
            raise OperationalError(sentinel)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(fail_lookup):
        api_client.post(reverse('verify_passcode_reset'), {
            'email': user.email, 'code': password_code.code, 'new_password': 'proposed-password',
        }, format='json')

    assert 'Password reset failed: error_type=OperationalError' in caplog.text
    assert sentinel not in caplog.text
    assert user.email not in caplog.text
    assert password_code.code not in caplog.text
    assert 'proposed-password' not in caplog.text
    assert 'Traceback' not in caplog.text


@pytest.mark.django_db
def test_verify_passcode_resets_password(api_client):
    """Verifies passcode verification resets the user password and marks the code as used on success."""
    User = get_user_model()
    user = User.objects.create_user(email='reset@example.com', password='pass1234')
    password_code = PasswordCode.generate_code(user)
    PasswordCode.objects.create(user=user, code=password_code.code)

    response = api_client.post(
        reverse('verify_passcode_reset'),
        {'email': user.email, 'code': password_code.code, 'new_password': 'newpass1'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    password_code.refresh_from_db()
    user.refresh_from_db()

    assert password_code.used is True
    assert user.check_password('newpass1') is True
    assert user.password_codes.filter(used=False).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('new_password', [
    'x', 'newpass', 12345678, ['x'] * 8, {'password': 'newpass1'}, True,
], ids=['one-character', 'seven-characters', 'integer', 'list', 'object', 'boolean'])
def test_verify_passcode_rejects_invalid_new_password(api_client, new_password):
    """Invalid new passwords preserve the original password and unused reset code."""
    user = get_user_model().objects.create_user(email='weak-reset@example.com', password='pass1234')
    password_code = PasswordCode.generate_code(user)

    response = api_client.post(
        reverse('verify_passcode_reset'),
        {'email': user.email, 'code': password_code.code, 'new_password': new_password},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Password must be at least 8 characters'
    user.refresh_from_db()
    password_code.refresh_from_db()
    assert user.check_password('pass1234') is True
    assert password_code.used is False


@pytest.mark.django_db
def test_verify_passcode_keeps_code_usable_after_password_rejection(api_client):
    """A rejected weak password does not prevent resetting with the same code."""
    user = get_user_model().objects.create_user(email='retry-reset@example.com', password='pass1234')
    password_code = PasswordCode.generate_code(user)

    rejected = api_client.post(
        reverse('verify_passcode_reset'),
        {'email': user.email, 'code': password_code.code, 'new_password': 'x'},
        format='json',
    )
    response = api_client.post(
        reverse('verify_passcode_reset'),
        {'email': user.email, 'code': password_code.code, 'new_password': 'newpass1'},
        format='json',
    )

    assert rejected.status_code == status.HTTP_400_BAD_REQUEST
    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    password_code.refresh_from_db()
    assert user.check_password('newpass1') is True
    assert password_code.used is True


@pytest.mark.django_db
def test_update_password_requires_fields(api_client):
    """Password updates require the current and replacement passwords."""
    User = get_user_model()
    user = User.objects.create_user(email='update-fields@example.com', password='pass1234')
    api_client.force_authenticate(user=user)

    response = api_client.post(reverse('update_password'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Current password and new password are required'


@pytest.mark.django_db
def test_update_password_rejects_wrong_current(api_client):
    """Password updates reject an incorrect current password."""
    User = get_user_model()
    user = User.objects.create_user(email='update@example.com', password='pass1234')

    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse('update_password'),
        {'current_password': 'wrong', 'new_password': 'newpass'},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Current password is incorrect'


@pytest.mark.django_db
def test_update_password_success(api_client):
    """Verifies update-password endpoint successfully changes the user password when the current password is correct."""
    User = get_user_model()
    user = User.objects.create_user(email='update2@example.com', password='pass1234')

    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse('update_password'),
        {'current_password': 'pass1234', 'new_password': 'newpass1'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password('newpass1') is True


@pytest.mark.django_db
@pytest.mark.parametrize('new_password', [
    'x', 'newpass', 12345678, ['x'] * 8, {'password': 'newpass1'}, True,
], ids=['one-character', 'seven-characters', 'integer', 'list', 'object', 'boolean'])
def test_update_password_rejects_invalid_new_password(api_client, new_password):
    """Invalid new passwords cannot replace an authenticated user's password."""
    user = get_user_model().objects.create_user(email='weak-update@example.com', password='pass1234')
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse('update_password'),
        {'current_password': 'pass1234', 'new_password': new_password},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Password must be at least 8 characters'
    user.refresh_from_db()
    assert user.check_password('pass1234') is True


@pytest.mark.django_db
def test_validate_token_requires_auth(api_client):
    """Token validation rejects unauthenticated requests."""
    response = api_client.get(reverse('validate_token'))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_validate_token_success(api_client):
    """Token validation accepts an authenticated user."""
    User = get_user_model()
    user = User.objects.create_user(email='token@example.com', password='pass1234')

    api_client.force_authenticate(user=user)
    response = api_client.get(reverse('validate_token'))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['valid'] is True


@pytest.mark.django_db
def test_failed_email_preserves_later_challenge(api_client, monkeypatch):
    """An older failed delivery cannot revoke a later reset challenge."""
    user = get_user_model().objects.create_user(email='later@example.com', password='pass1234')
    later = {}

    def fail_after_resend(*_args):
        later['challenge'] = PasswordCode.generate_code(user)
        return False

    monkeypatch.setattr(auth_views, 'send_password_reset_code', fail_after_resend)
    response = api_client.post(reverse('send_passcode'), {'email': user.email}, format='json')

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    challenge = later['challenge']
    challenge.refresh_from_db()
    assert challenge.is_valid() is True
    assert list(user.password_codes.filter(used=False).values_list('pk', flat=True)) == [challenge.pk]


@pytest.mark.django_db
def test_verify_passcode_rejects_replay(api_client):
    """A consumed token cannot overwrite the successfully reset password."""
    user = get_user_model().objects.create_user(email='replay@example.com', password='pass1234')
    challenge = PasswordCode.generate_code(user)
    accepted = api_client.post(reverse('verify_passcode_reset'), {
        'email': user.email, 'code': challenge.code, 'new_password': 'first-password',
    }, format='json')

    response = api_client.post(reverse('verify_passcode_reset'), {
        'email': user.email, 'code': challenge.code, 'new_password': 'second-password',
    }, format='json')

    assert accepted.status_code == status.HTTP_200_OK
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    user.refresh_from_db()
    assert user.check_password('first-password') is True


@pytest.mark.django_db
def test_verify_invalid_code_does_not_log(api_client, caplog):
    """An ordinary rejected token does not generate an internal-error log."""
    user = get_user_model().objects.create_user(email='quiet@example.com', password='pass1234')
    challenge = PasswordCode.generate_code(user)
    caplog.set_level(logging.ERROR, logger=auth_views.__name__)

    response = api_client.post(reverse('verify_passcode_reset'), {
        'email': user.email, 'code': 'invalid-token', 'new_password': 'new-password',
    }, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['error'] == 'Invalid or expired code'
    assert 'Password reset failed' not in caplog.text
    challenge.refresh_from_db()
    assert challenge.used is False
