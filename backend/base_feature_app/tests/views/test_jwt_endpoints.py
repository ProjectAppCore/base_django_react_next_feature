"""Verify JWT issuance for valid email credentials."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_token_obtain_pair_with_email_success(api_client):
    """Valid email credentials issue a JWT access and refresh token pair."""
    User = get_user_model()
    User.objects.create_user(email='token@example.com', password='pass1234')

    url = reverse('token_obtain_pair')
    response = api_client.post(url, {'email': 'token@example.com', 'password': 'pass1234'}, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert 'access' in response.json()
    assert 'refresh' in response.json()
