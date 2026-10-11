"""Verify password-code generation, display, and validity boundaries."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from freezegun import freeze_time

from base_feature_app.models import PasswordCode


@pytest.mark.django_db
def test_password_code_str_representation():
    """The password-code string identifies its user and code."""
    User = get_user_model()
    user = User.objects.create_user(email='code@example.com', password='pass1234')
    password_code = PasswordCode.objects.create(user=user, code='123456')

    assert str(password_code) == 'Code for code@example.com - 123456'


@pytest.mark.django_db
def test_password_code_generate_code_creates_valid_token():
    """Generated challenges contain a Django token for the account."""
    user = get_user_model().objects.create_user(email='generate@example.com', password='pass1234')

    password_code = PasswordCode.generate_code(user)

    assert default_token_generator.check_token(user, password_code.code) is True
    assert len(password_code.code) <= 64
    assert password_code.code.isdigit() is False


@pytest.mark.django_db
def test_password_code_generation_replaces_previous_challenge():
    """A resend revokes the previous challenge row."""
    user = get_user_model().objects.create_user(email='resend@example.com', password='pass1234')
    previous = PasswordCode.generate_code(user)

    current = PasswordCode.generate_code(user)

    previous.refresh_from_db()
    assert previous.is_valid() is False
    assert current.is_valid() is True
    assert user.password_codes.filter(used=False).count() == 1


@pytest.mark.django_db
def test_password_code_rejects_legacy_six_digits():
    """Recent numeric challenges cannot bypass token verification."""
    user = get_user_model().objects.create_user(email='legacy@example.com', password='pass1234')
    password_code = PasswordCode.objects.create(user=user, code='123456')

    assert password_code.is_valid() is False


@pytest.mark.django_db
def test_password_code_rejects_changed_password():
    """Changing the account password invalidates an otherwise recent token."""
    user = get_user_model().objects.create_user(email='changed@example.com', password='pass1234')
    password_code = PasswordCode.generate_code(user)
    user.set_password('differentpass')
    user.save(update_fields=['password'])
    password_code.refresh_from_db()

    assert password_code.is_valid() is False


@pytest.mark.django_db
def test_password_code_is_valid_false_when_used():
    """A used password code is no longer valid."""
    User = get_user_model()
    user = User.objects.create_user(email='used@example.com', password='pass1234')
    password_code = PasswordCode.objects.create(user=user, code='654321', used=True)

    assert password_code.is_valid() is False


@pytest.mark.django_db
@freeze_time('2026-01-15 10:00:00')
def test_password_code_is_valid_false_when_expired():
    """A password code past its expiry window is invalid."""
    User = get_user_model()
    user = User.objects.create_user(email='expired@example.com', password='pass1234')
    password_code = PasswordCode.generate_code(user)
    PasswordCode.objects.filter(id=password_code.id).update(
        created_at=timezone.now() - timedelta(minutes=16)
    )
    password_code.refresh_from_db()

    assert password_code.is_valid() is False


@pytest.mark.django_db
def test_password_code_is_valid_true_for_recent_code():
    """A recent unused password code remains valid."""
    User = get_user_model()
    user = User.objects.create_user(email='valid@example.com', password='pass1234')
    password_code = PasswordCode.generate_code(user)

    assert password_code.is_valid() is True


@pytest.mark.django_db
@freeze_time('2026-01-15 10:00:00')
def test_password_code_rejects_exact_expiry_boundary():
    """A token becomes invalid exactly fifteen minutes after issuance."""
    user = get_user_model().objects.create_user(email='boundary@example.com', password='pass1234')
    password_code = PasswordCode.generate_code(user)
    PasswordCode.objects.filter(pk=password_code.pk).update(
        created_at=timezone.now() - timedelta(minutes=15),
    )
    password_code.refresh_from_db()

    assert password_code.is_valid() is False


@pytest.mark.django_db(transaction=True)
def test_secure_token_migration_retires_legacy_challenges():
    """The schema upgrade permanently retires all outstanding numeric codes."""
    from django.db import connection, connections
    from django.db.backends.sqlite3.base import DatabaseWrapper
    from django.db.migrations.exceptions import IrreversibleError
    from django.db.migrations.executor import MigrationExecutor

    alias = 'password_reset_migration_probe'
    configuration = connection.settings_dict.copy()
    configuration.update(ENGINE='django.db.backends.sqlite3', NAME=':memory:', OPTIONS={})
    probe = DatabaseWrapper(configuration, alias)
    connections[alias] = probe
    previous = [('base_feature_app', '0005_create_staging_phase_banner')]
    current = [('base_feature_app', '0006_passwordcode_secure_tokens')]
    executor = MigrationExecutor(probe)
    try:
        executor.migrate(previous)
        historical_apps = executor.loader.project_state(previous).apps
        HistoricalUser = historical_apps.get_model('base_feature_app', 'User')
        HistoricalCode = historical_apps.get_model('base_feature_app', 'PasswordCode')
        user = HistoricalUser.objects.using(alias).create(email='migration@example.invalid', password='synthetic-hash')
        pending = HistoricalCode.objects.using(alias).create(user=user, code='123456', used=False)
        consumed = HistoricalCode.objects.using(alias).create(user=user, code='654321', used=True)

        executor = MigrationExecutor(probe)
        executor.migrate(current)

        apps = executor.loader.project_state(current).apps
        SecureCode = apps.get_model('base_feature_app', 'PasswordCode')
        assert SecureCode.objects.using(alias).get(pk=pending.pk).used is True
        assert SecureCode.objects.using(alias).get(pk=consumed.pk).used is True
        assert SecureCode._meta.get_field('code').max_length == 64
        SecureCode.objects.using(alias).create(user_id=user.pk, code='a' * 64)
        with pytest.raises(IrreversibleError):
            MigrationExecutor(probe).migrate(previous)
        assert SecureCode.objects.using(alias).get(pk=pending.pk).used is True
    finally:
        MigrationExecutor(probe).migrate(current)
        probe.close()
        del connections[alias]
