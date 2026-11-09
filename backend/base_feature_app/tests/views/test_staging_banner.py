"""Tests for the public staging phase banner endpoint."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework import status

from base_feature_app.models import StagingPhaseBanner


@pytest.fixture
def banner(db):
    """Provide the singleton staging banner row with its default field values."""
    instance, _ = StagingPhaseBanner.objects.get_or_create(pk=1)
    return instance


@pytest.mark.django_db
def test_staging_banner_endpoint_returns_200(api_client, banner):
    """The staging banner endpoint answers an anonymous GET with 200 OK."""
    url = reverse('staging-banner')

    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_staging_banner_inactive_when_started_at_is_null(api_client, banner):
    """A banner without started_at reports no countdown and is not expired."""
    banner.started_at = None
    banner.save()
    url = reverse('staging-banner')

    response = api_client.get(url)

    body = response.json()
    assert body['started_at'] is None
    assert body['days_remaining'] is None
    assert body['is_expired'] is False


@pytest.mark.django_db
@freeze_time('2026-01-15 10:00:00')
def test_staging_banner_active_design_phase_returns_remaining_days(api_client, banner):
    """Report days_remaining equal to design_duration_days under a frozen clock.

    Catches an off-by-one in the ceil()'d day math that a live clock could mask
    between the test's and the model's independent timezone.now() reads.
    """
    banner.current_phase = StagingPhaseBanner.PHASE_DESIGN
    banner.started_at = timezone.now()
    banner.save()
    url = reverse('staging-banner')

    response = api_client.get(url)

    body = response.json()
    assert body['current_phase'] == StagingPhaseBanner.PHASE_DESIGN
    assert body['phase_labels'] == {'es': 'Etapa de diseño', 'en': 'Design phase'}
    assert body['is_expired'] is False
    assert body['days_remaining'] == banner.design_duration_days


@pytest.mark.django_db
@freeze_time('2026-01-15 10:00:00')
def test_staging_banner_expired_when_phase_window_elapsed(api_client, banner):
    """Resolve is_expired and days_remaining against the frozen started_at instant.

    Catches a day-math regression in is_expired that a live clock could mask
    between the test's and the model's independent timezone.now() reads.
    """
    banner.current_phase = StagingPhaseBanner.PHASE_DEVELOPMENT
    banner.started_at = timezone.now() - timedelta(days=banner.development_duration_days + 1)
    banner.save()
    url = reverse('staging-banner')

    response = api_client.get(url)

    body = response.json()
    assert body['is_expired'] is True
    assert body['days_remaining'] == 0


@pytest.mark.django_db
def test_staging_banner_exposes_contact_details(api_client, banner):
    """The banner payload exposes the public WhatsApp and email contact details."""
    url = reverse('staging-banner')

    response = api_client.get(url)

    body = response.json()
    assert body['contact_whatsapp'] == '+57 323 8122373'
    assert body['contact_email'] == 'contact@example.com'


@pytest.mark.django_db
def test_staging_banner_does_not_expose_internal_duration_config(api_client, banner):
    """The banner payload omits internal duration fields and exposes exactly the public contract.

    A negation-only check on the two internal fields is satisfied by an empty
    body, so it would miss a regression that dropped the whole payload. Pinning
    the exact key set catches that, plus any other internal field (present or
    future) that leaks in alongside `design_duration_days`/`development_duration_days`.
    """
    url = reverse('staging-banner')

    response = api_client.get(url)

    body = response.json()
    assert 'design_duration_days' not in body
    assert 'development_duration_days' not in body
    assert set(body.keys()) == {
        'is_visible',
        'current_phase',
        'phase_labels',
        'started_at',
        'expires_at',
        'days_remaining',
        'is_expired',
        'contact_whatsapp',
        'contact_email',
    }
