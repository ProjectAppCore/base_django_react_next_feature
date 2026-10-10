import io

import pytest
from django.core.files.base import ContentFile
from django_attachments.models import Attachment, Library
from PIL import Image

from base_feature_app.models import Blog, Product


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    """Keep attachment files inside this test's temporary directory."""
    settings.MEDIA_ROOT = str(tmp_path / 'media')


def _placeholder_image(name='placeholder.webp'):
    image = Image.new('RGB', (10, 10), color=(240, 240, 240))
    buffer = io.BytesIO()
    image.save(buffer, format='WEBP')
    buffer.seek(0)
    return ContentFile(buffer.read(), name=name)


@pytest.mark.django_db
def test_blog_delete_removes_library():
    library = Library.objects.create(title='Blog Image')
    Attachment.objects.create(library=library, file=_placeholder_image(), original_name='placeholder.webp', rank=0)
    blog = Blog.objects.create(title='T', description='D', category='C', image=library)

    library_id = library.id
    blog.delete()

    assert not Library.objects.filter(id=library_id).exists()


@pytest.mark.django_db
def test_blog_str_representation():
    library = Library.objects.create(title='Blog Image')
    blog = Blog.objects.create(title='My Blog', description='D', category='C', image=library)

    assert str(blog) == 'My Blog'


@pytest.mark.django_db
def test_blog_delete_handles_missing_library():
    library = Library.objects.create(title='Blog Image')
    blog = Blog.objects.create(title='T', description='D', category='C', image=library)

    Blog.objects.filter(id=blog.id).update(image_id=9999)
    blog.refresh_from_db()

    blog.delete()

    assert not Blog.objects.filter(id=blog.id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('create_survivor', [
    pytest.param(
        lambda library: Blog.objects.create(title='Survivor', description='D', category='C', image=library),
        id='blog',
    ),
    pytest.param(
        lambda library: Product.objects.create(
            title='Survivor', description='D', category='C', sub_category='S', price=10, gallery=library,
        ),
        id='product',
    ),
])
def test_blog_delete_preserves_shared_library(create_survivor):
    """Deleting a blog preserves the library still used by another owner."""
    library = Library.objects.create(title='Shared image')
    attachment = Attachment.objects.create(library=library, file=_placeholder_image(), rank=0)
    blog = Blog.objects.create(title='Deleted', description='D', category='C', image=library)
    blog_id = blog.pk
    survivor = create_survivor(library)

    result = blog.delete(using='default')

    assert result is None
    assert not Blog.objects.filter(pk=blog_id).exists()
    assert type(survivor).objects.filter(pk=survivor.pk).exists()
    assert Library.objects.filter(pk=library.pk).exists()
    assert Attachment.objects.filter(pk=attachment.pk, library=library).exists()
    assert attachment.file.storage.exists(attachment.file.name)


@pytest.mark.django_db
def test_blog_delete_cleans_library_after_last_owner():
    """Removing the final blog cleans its formerly shared library."""
    library = Library.objects.create(title='Shared image')
    attachment = Attachment.objects.create(library=library, file=_placeholder_image(), rank=0)
    first = Blog.objects.create(title='First', description='D', category='C', image=library)
    last = Blog.objects.create(title='Last', description='D', category='C', image=library)
    first.delete()

    last.delete()

    assert not Library.objects.filter(pk=library.pk).exists()
    assert not Attachment.objects.filter(pk=attachment.pk).exists()
    assert not attachment.file.storage.exists(attachment.file.name)
