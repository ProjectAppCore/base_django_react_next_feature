"""Verify user serializer creation and update behavior."""

import pytest

from base_feature_app.models import User
from base_feature_app.serializers.user_create_update import UserCreateUpdateSerializer


@pytest.mark.django_db
def test_user_create_update_serializer_creates_with_password():
    """Verifies UserCreateUpdateSerializer creates a user with a properly hashed password."""
    payload = {
        'email': 'created@example.com',
        'password': 'pass1234',
        'first_name': 'First',
        'last_name': 'Last',
        'phone': '123',
        'role': User.Role.CUSTOMER,
    }

    serializer = UserCreateUpdateSerializer(data=payload)

    assert serializer.is_valid(), serializer.errors
    user = serializer.save()

    assert user.check_password('pass1234') is True


@pytest.mark.django_db
def test_user_create_update_serializer_updates_password_and_fields():
    """Updating a user persists the supplied password and profile fields."""
    user = User.objects.create_user(email='update@example.com', password='oldpass')

    serializer = UserCreateUpdateSerializer(
        instance=user,
        data={'first_name': 'Updated', 'password': 'newpass'},
        partial=True,
    )

    assert serializer.is_valid(), serializer.errors
    updated = serializer.save()

    assert updated.first_name == 'Updated'
    assert updated.check_password('newpass') is True


@pytest.mark.django_db
def test_user_create_update_serializer_updates_without_password():
    """Updating profile fields preserves the user's existing password."""
    user = User.objects.create_user(email='nopass@example.com', password='oldpass')

    serializer = UserCreateUpdateSerializer(
        instance=user,
        data={'last_name': 'NoPass'},
        partial=True,
    )

    assert serializer.is_valid(), serializer.errors
    updated = serializer.save()

    assert updated.last_name == 'NoPass'
    assert updated.check_password('oldpass') is True
