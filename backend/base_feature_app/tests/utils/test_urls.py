"""Verify the legacy URL module remains executable."""

import importlib
import importlib.util
from pathlib import Path

import pytest


@pytest.mark.django_db
def test_url_modules_import_and_have_patterns():
    """Verifies each URL sub-module imports successfully and registers the expected named patterns."""
    package_urls = importlib.import_module('base_feature_app.urls')
    assert hasattr(package_urls, 'urlpatterns')

    auth_urls = importlib.import_module('base_feature_app.urls.auth')
    blog_urls = importlib.import_module('base_feature_app.urls.blog')
    product_urls = importlib.import_module('base_feature_app.urls.product')
    sale_urls = importlib.import_module('base_feature_app.urls.sale')
    user_urls = importlib.import_module('base_feature_app.urls.user')

    assert any(pattern.name == 'sign_up' for pattern in auth_urls.urlpatterns)
    assert any(pattern.name == 'blog-list' for pattern in blog_urls.urlpatterns)
    assert any(pattern.name == 'product-list' for pattern in product_urls.urlpatterns)
    assert any(pattern.name == 'sale-list' for pattern in sale_urls.urlpatterns)
    assert any(pattern.name == 'user-list' for pattern in user_urls.urlpatterns)


@pytest.mark.django_db
def test_module_urls_py_is_executable():
    """The legacy URL module executes without raising an error."""
    urls_path = Path(__file__).resolve().parents[2] / 'urls.py'
    spec = importlib.util.spec_from_file_location('base_feature_app.urls_module', urls_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert hasattr(module, 'urlpatterns')
    names = [pattern.url_patterns for pattern in module.urlpatterns]
    assert len(names) >= 1
