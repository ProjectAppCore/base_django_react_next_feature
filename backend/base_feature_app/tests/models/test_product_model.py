"""Verify product display and gallery cleanup."""

import io
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.db.models.deletion import ProtectedError
from django_attachments.models import Attachment, Library
from PIL import Image

from base_feature_app.models import Blog, Product, SoldProduct


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    """Keep attachment files inside this test's temporary directory."""
    settings.MEDIA_ROOT = str(tmp_path / 'media')


def _create_product(gallery, title='Product'):
    """Create a product referencing the supplied gallery."""
    return Product.objects.create(
        title=title, category='C', sub_category='S', description='D', price=10, gallery=gallery,
    )


def _placeholder_image(name='placeholder.webp'):
    image = Image.new('RGB', (10, 10), color=(240, 240, 240))
    buffer = io.BytesIO()
    image.save(buffer, format='WEBP')
    buffer.seek(0)
    return ContentFile(buffer.read(), name=name)


@pytest.mark.django_db
def test_product_delete_removes_library_and_attachments():
    """Verifies that deleting a product also removes its associated library and all attachments."""
    gallery = Library.objects.create(title='Product Gallery')
    Attachment.objects.create(library=gallery, file=_placeholder_image(), original_name='placeholder.webp', rank=0)
    product = Product.objects.create(
        title='T',
        category='C',
        sub_category='S',
        description='D',
        price=10,
        gallery=gallery,
    )

    gallery_id = gallery.id
    product.delete()

    assert not Library.objects.filter(id=gallery_id).exists()
    assert not Attachment.objects.filter(library_id=gallery_id).exists()


@pytest.mark.django_db
def test_product_str_representation():
    """The product string representation uses its title."""
    gallery = Library.objects.create(title='Gallery')
    product = Product.objects.create(
        title='My Product',
        category='C',
        sub_category='S',
        description='D',
        price=10,
        gallery=gallery,
    )

    assert str(product) == 'My Product'


@pytest.mark.django_db
def test_product_delete_handles_missing_gallery():
    """Verifies that deleting a product with a non-existent gallery reference does not raise an error."""
    gallery = Library.objects.create(title='Gallery')
    product = Product.objects.create(
        title='T',
        category='C',
        sub_category='S',
        description='D',
        price=10,
        gallery=gallery,
    )

    Product.objects.filter(id=product.id).update(gallery_id=9999)
    product.refresh_from_db()

    product.delete()

    assert not Product.objects.filter(id=product.id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('create_survivor', [
    pytest.param(lambda library: _create_product(library, title='Survivor'), id='product'),
    pytest.param(
        lambda library: Blog.objects.create(title='Survivor', description='D', category='C', image=library),
        id='blog',
    ),
])
def test_product_delete_preserves_shared_library(create_survivor):
    """Deleting a product preserves the gallery still used by another owner."""
    library = Library.objects.create(title='Shared gallery')
    attachment = Attachment.objects.create(library=library, file=_placeholder_image(), rank=0)
    product = _create_product(library)
    product_id = product.pk
    survivor = create_survivor(library)

    result = product.delete(using='default')

    assert result is None
    assert not Product.objects.filter(pk=product_id).exists()
    assert type(survivor).objects.filter(pk=survivor.pk).exists()
    assert Library.objects.filter(pk=library.pk).exists()
    assert Attachment.objects.filter(pk=attachment.pk, library=library).exists()
    assert attachment.file.storage.exists(attachment.file.name)


@pytest.mark.django_db
def test_product_delete_cleans_library_after_last_owner(django_capture_on_commit_callbacks):
    """Removing the final product cleans its formerly shared gallery."""
    library = Library.objects.create(title='Shared gallery')
    attachment = Attachment.objects.create(library=library, file=_placeholder_image(), rank=0)
    first = _create_product(library, title='First')
    last = _create_product(library, title='Last')
    first.delete()

    with django_capture_on_commit_callbacks(execute=True):
        last.delete()

    assert not Library.objects.filter(pk=library.pk).exists()
    assert not Attachment.objects.filter(pk=attachment.pk).exists()
    assert not attachment.file.storage.exists(attachment.file.name)


@pytest.mark.django_db
def test_product_delete_preserves_media_when_protected():
    """A sold product cannot delete its gallery before PROTECT rejects deletion."""
    library = Library.objects.create(title='Protected gallery')
    attachment = Attachment.objects.create(library=library, file=_placeholder_image(), rank=0)
    product = _create_product(library)
    sold_product = SoldProduct.objects.create(product=product, quantity=1)
    file_path = Path(attachment.file.path)
    original_content = file_path.read_bytes()

    with pytest.raises(ProtectedError):
        product.delete(using='default')

    assert Product.objects.filter(pk=product.pk, gallery=library).exists()
    assert Library.objects.filter(pk=library.pk).exists()
    assert Attachment.objects.filter(pk=attachment.pk, library=library).exists()
    assert SoldProduct.objects.filter(pk=sold_product.pk, product=product).exists()
    assert file_path.read_bytes() == original_content
