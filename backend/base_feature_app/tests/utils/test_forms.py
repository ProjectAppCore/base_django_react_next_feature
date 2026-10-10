"""Verify user form password handling."""

import builtins

import pytest
from django.conf import settings as django_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django_attachments.models import Attachment, Library

from base_feature_app.forms.blog import BlogForm
from base_feature_app.forms.product import ProductForm
from base_feature_app.forms.user import UserChangeForm, UserCreationForm
from base_feature_app.models import Blog, Product, User


def _create_attachment(library, filename='file.txt'):
    return Attachment.objects.create(
        library=library,
        original_name=filename,
        file=SimpleUploadedFile(filename, b'content'),
        rank=0,
    )


@pytest.mark.django_db
def test_blog_form_clean_image_rejects_multiple_attachments(monkeypatch, tmp_path):
    """Verifies BlogForm validation rejects a library that contains more than one attachment."""
    monkeypatch.setattr(django_settings, 'MEDIA_ROOT', tmp_path)
    library = Library.objects.create(title='Blog Library')
    _create_attachment(library, 'one.txt')
    _create_attachment(library, 'two.txt')

    form = BlogForm(
        data={
            'title': 'Test Blog',
            'description': 'Desc',
            'category': 'Cat',
            'image': library.id,
        }
    )

    assert form.is_valid() is False
    assert 'image' in form.errors


@pytest.mark.django_db
def test_blog_form_save_creates_library_when_missing_attribute(tmp_path, monkeypatch):
    """Verifies BlogForm.save() creates a new Library when the blog instance has no image attribute."""
    monkeypatch.setattr(django_settings, 'MEDIA_ROOT', tmp_path)
    library = Library.objects.create(title='Existing')

    form = BlogForm(
        data={
            'title': 'Test Blog',
            'description': 'Desc',
            'category': 'Cat',
            'image': library.id,
        }
    )

    assert form.is_valid() is True

    original_hasattr = builtins.hasattr
    monkeypatch.setattr(
        builtins,
        'hasattr',
        lambda obj, name: False if name == 'image' else original_hasattr(obj, name),
    )

    blog = form.save()

    assert isinstance(blog, Blog)
    assert blog.image is not None
    assert Library.objects.count() == 2


@pytest.mark.django_db
def test_product_form_save_creates_gallery_when_missing_attribute(tmp_path, monkeypatch):
    """Verifies ProductForm.save() creates a new Library when the product instance has no gallery attribute."""
    monkeypatch.setattr(django_settings, 'MEDIA_ROOT', tmp_path)
    library = Library.objects.create(title='Existing')

    form = ProductForm(
        data={
            'title': 'Test Product',
            'category': 'Cat',
            'sub_category': 'Sub',
            'description': 'Desc',
            'price': 120,
            'gallery': library.id,
        }
    )

    assert form.is_valid() is True

    original_hasattr = builtins.hasattr
    monkeypatch.setattr(
        builtins,
        'hasattr',
        lambda obj, name: False if name == 'gallery' else original_hasattr(obj, name),
    )

    product = form.save()

    assert isinstance(product, Product)
    assert product.gallery is not None
    assert Library.objects.count() == 2


@pytest.mark.django_db
def test_user_creation_form_validates_password_confirmation():
    """Verifies UserCreationForm is invalid when the two password fields do not match."""
    form = UserCreationForm(
        data={
            'email': 'user@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '123',
            'role': User.Role.CUSTOMER,
            'password1': 'pass1234',
            'password2': 'pass9999',
        }
    )

    assert form.is_valid() is False
    assert 'password2' in form.errors


@pytest.mark.django_db
def test_user_creation_form_saves_hashed_password():
    """Verifies UserCreationForm hashes the password when saving a new user."""
    form = UserCreationForm(
        data={
            'email': 'user@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '123',
            'role': User.Role.CUSTOMER,
            'password1': 'pass1234',
            'password2': 'pass1234',
        }
    )

    assert form.is_valid() is True
    user = form.save()

    assert user.check_password('pass1234') is True


@pytest.mark.django_db
def test_user_change_form_returns_initial_password():
    """The user change form preserves the initial encoded password."""
    user = User.objects.create_user(email='change@example.com', password='pass1234')
    form = UserChangeForm(instance=user, initial={'password': user.password})

    assert form.clean_password() == user.password
