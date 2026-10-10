"""Verify password-code generation, display, and validity boundaries."""

import random
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
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
def test_password_code_generate_code_creates_six_digits(monkeypatch):
    """Generated password codes contain exactly six numeric characters."""
    User = get_user_model()
    user = User.objects.create_user(email='generate@example.com', password='pass1234')

    monkeypatch.setattr(random, 'randint', lambda *_: 1)

    password_code = PasswordCode.generate_code(user)

    assert password_code.code == '111111'


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
    password_code = PasswordCode.objects.create(user=user, code='654321')
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
    password_code = PasswordCode.objects.create(user=user, code='654321')

    assert password_code.is_valid() is True
