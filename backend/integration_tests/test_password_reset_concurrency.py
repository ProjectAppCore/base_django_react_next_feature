"""Explicit integration checks requiring a fresh, isolated MySQL test database."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from base_feature_app.models import PasswordCode
from base_feature_app.views import auth as auth_views
from django.contrib.auth import get_user_model
from django.db import OperationalError, close_old_connections, connection, connections
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def reset_user(transactional_db):
    """Require MySQL so a SQLite run cannot claim row-lock verification."""
    assert connection.vendor == 'mysql', 'Run explicitly against isolated MySQL.'
    return get_user_model().objects.create_user(
        email='concurrency@example.invalid', password='original-password',
    )


def run_concurrently(operation):
    """Start requests before either reaches the account lock."""
    barrier = Barrier(2)

    def worker(index):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return operation(index)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker, index) for index in range(2)]
        return [future.result(timeout=30) for future in futures]


def test_concurrent_reset_consumes_token_once(reset_user):
    """Two competing verifications produce exactly one password reset."""
    challenge = PasswordCode.generate_code(reset_user)

    def reset(index):
        password = f'new-password-{index}'
        response = APIClient().post(reverse('verify_passcode_reset'), {
            'email': reset_user.email, 'code': challenge.code, 'new_password': password,
        }, format='json')
        return response.status_code, password

    outcomes = run_concurrently(reset)

    assert sorted(status for status, _password in outcomes) == [200, 400]
    winner_password = next(password for status, password in outcomes if status == 200)
    reset_user.refresh_from_db()
    challenge.refresh_from_db()
    assert reset_user.check_password(winner_password) is True
    assert challenge.used is True
    assert reset_user.password_codes.filter(used=False).count() == 0


def test_concurrent_emissions_leave_one_active_challenge(reset_user, monkeypatch):
    """Competing send requests cannot accumulate active challenge rows."""
    monkeypatch.setattr(auth_views, 'send_password_reset_code', lambda *_args: True)

    def send(_index):
        return APIClient().post(reverse('send_passcode'), {
            'email': reset_user.email,
        }, format='json').status_code

    statuses = run_concurrently(send)

    assert statuses == [200, 200]
    assert reset_user.password_codes.count() == 2
    assert reset_user.password_codes.filter(used=False).count() == 1
    assert reset_user.password_codes.get(used=False).is_valid() is True


def test_reset_consumption_failure_rolls_back_password(reset_user):
    """A failed challenge update rolls back the already-issued password write."""
    challenge = PasswordCode.generate_code(reset_user)
    original_hash = reset_user.password

    def fail_consumption(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith('UPDATE') and 'base_feature_app_passwordcode' in sql:
            raise OperationalError('synthetic consumption failure')
        return execute(sql, params, many, context)

    with connection.execute_wrapper(fail_consumption):
        response = APIClient().post(reverse('verify_passcode_reset'), {
            'email': reset_user.email, 'code': challenge.code, 'new_password': 'new-password',
        }, format='json')

    assert response.status_code == 400
    assert response.json() == {'error': 'Invalid or expired code'}
    reset_user.refresh_from_db()
    challenge.refresh_from_db()
    assert reset_user.password == original_hash
    assert challenge.is_valid() is True
