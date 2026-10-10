"""Verify product serializer gallery URLs and missing-gallery responses."""

import io
from types import SimpleNamespace

import pytest
from django.conf import settings as django_settings
from django.core.files.base import ContentFile
from django_attachments.models import Attachment, Library
from PIL import Image
from rest_framework.test import APIRequestFactory

from base_feature_app.models import Product
from base_feature_app.serializers.product import ProductSerializer
from base_feature_app.serializers.product_detail import ProductDetailSerializer
from base_feature_app.serializers.product_list import ProductListSerializer


def _placeholder_image(name='placeholder.webp'):
    image = Image.new('RGB', (10, 10), color=(240, 240, 240))
    buffer = io.BytesIO()
    image.save(buffer, format='WEBP')
    buffer.seek(0)
    return ContentFile(buffer.read(), name=name)


@pytest.mark.django_db
def test_product_list_serializer_gallery_urls_empty_without_request():
    """Product list serialization omits gallery URLs without a request."""
    gallery = Library.objects.create(title='Gallery')
    Attachment.objects.create(library=gallery, file=_placeholder_image(), original_name='placeholder.webp', rank=0)
    product = Product.objects.create(
        title='P',
        category='C',
        sub_category='S',
        description='D',
        price=10,
        gallery=gallery,
    )

    serializer = ProductListSerializer(product)
    assert serializer.data['gallery_urls'] == []


@pytest.mark.django_db
def test_product_list_serializer_includes_gallery_urls(monkeypatch, tmp_path):
    """Verifies ProductListSerializer returns absolute gallery URLs when a request context is provided."""
    monkeypatch.setattr(django_settings, 'MEDIA_ROOT', tmp_path)
    gallery = Library.objects.create(title='Gallery')
    Attachment.objects.create(library=gallery, file=_placeholder_image(), original_name='placeholder.webp', rank=0)
    product = Product.objects.create(
        title='P',
        category='C',
        sub_category='S',
        description='D',
        price=10,
        gallery=gallery,
    )

    factory = APIRequestFactory()
    request = factory.get('/api/products/')

    serializer = ProductListSerializer(product, context={'request': request})

    assert serializer.data['gallery_urls']
    assert serializer.data['gallery_urls'][0].startswith('http://testserver/')


@pytest.mark.django_db
def test_product_serializer_returns_empty_without_request():
    """Product serialization returns an empty gallery without a request."""
    gallery = Library.objects.create(title='Gallery')
    product = Product.objects.create(
        title='P',
        category='C',
        sub_category='S',
        description='D',
        price=10,
        gallery=gallery,
    )

    serializer = ProductSerializer(product)

    assert serializer.data['gallery_urls'] == []


@pytest.mark.django_db
def test_product_serializer_returns_empty_without_gallery():
    """Product serialization returns an empty gallery when no library exists."""
    factory = APIRequestFactory()
    request = factory.get('/api/products/')

    serializer = ProductSerializer(context={'request': request})
    product = SimpleNamespace(gallery=None)

    assert serializer.get_gallery_urls(product) == []


@pytest.mark.django_db
def test_product_detail_serializer_returns_empty_without_request():
    """Product detail serialization returns an empty gallery without a request."""
    gallery = Library.objects.create(title='Gallery')
    product = Product.objects.create(
        title='P',
        category='C',
        sub_category='S',
        description='D',
        price=10,
        gallery=gallery,
    )

    serializer = ProductDetailSerializer(product)

    assert serializer.data['gallery_urls'] == []


@pytest.mark.django_db
def test_product_detail_serializer_returns_empty_without_gallery():
    """Product detail serialization returns an empty gallery without a library."""
    factory = APIRequestFactory()
    request = factory.get('/api/products/')

    serializer = ProductDetailSerializer(context={'request': request})
    product = SimpleNamespace(gallery=None)

    assert serializer.get_gallery_urls(product) == []


@pytest.mark.django_db
def test_product_list_serializer_returns_empty_without_gallery():
    """Product list serialization returns an empty gallery without a library."""
    factory = APIRequestFactory()
    request = factory.get('/api/products/')

    serializer = ProductListSerializer(context={'request': request})
    product = SimpleNamespace(gallery=None)

    assert serializer.get_gallery_urls(product) == []


@pytest.mark.django_db
def test_product_detail_serializer_includes_gallery_urls(monkeypatch, tmp_path):
    """Verifies ProductDetailSerializer returns absolute gallery URLs when a request context is provided."""
    monkeypatch.setattr(django_settings, 'MEDIA_ROOT', tmp_path)
    gallery = Library.objects.create(title='Gallery')
    Attachment.objects.create(library=gallery, file=_placeholder_image(), original_name='placeholder.webp', rank=0)
    product = Product.objects.create(
        title='P',
        category='C',
        sub_category='S',
        description='D',
        price=10,
        gallery=gallery,
    )

    factory = APIRequestFactory()
    request = factory.get('/api/products/')

    serializer = ProductDetailSerializer(product, context={'request': request})

    assert serializer.data['gallery_urls']
    assert serializer.data['gallery_urls'][0].startswith('http://testserver/')
