"""Verify admin deletion, display, and impersonation permissions."""

import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.test import RequestFactory
from django_attachments.models import Attachment, Library

from base_feature_app.admin import (
    BaseFeatureUserAdmin,
    BlogAdmin,
    PasswordCodeAdmin,
    ProductAdmin,
    SaleAdmin,
    admin_site,
)
from base_feature_app.models import Blog, PasswordCode, Product, Sale, SoldProduct, User


@pytest.fixture(params=[
    pytest.param(
        (Blog, BlogAdmin, lambda library, title: Blog.objects.create(
            title=title, description='D', category='C', image=library,
        )),
        id='blog',
    ),
    pytest.param(
        (Product, ProductAdmin, lambda library, title: Product.objects.create(
            title=title, description='D', category='C', sub_category='S', price=10, gallery=library,
        )),
        id='product',
    ),
])
def library_owners(request, settings, tmp_path, db):
    """Create admin owners sharing one library with a real attachment."""
    settings.MEDIA_ROOT = str(tmp_path / 'media')
    model, admin_type, create_owner = request.param
    library = Library.objects.create(title='Shared media')
    attachment = Attachment.objects.create(
        library=library, file=ContentFile(b'Shared content', name='shared.txt'), rank=0,
    )
    first = create_owner(library, 'First')
    second = create_owner(library, 'Second')
    return model, admin_type(model, admin_site), library, attachment, first, second, create_owner


@pytest.fixture
def sale_owners(db):
    """Create admin sales sharing a sold product."""
    library = Library.objects.create(title='Product media')
    product = Product.objects.create(
        title='Product', description='D', category='C', sub_category='S', price=10, gallery=library,
    )
    line = SoldProduct.objects.create(product=product, quantity=2)
    first = Sale.objects.create(email='first@example.com', address='A', city='C', state='S', postal_code='1')
    second = Sale.objects.create(email='second@example.com', address='A', city='C', state='S', postal_code='1')
    first.sold_products.add(line)
    second.sold_products.add(line)
    return SaleAdmin(Sale, admin_site), line, first, second


def _request_with_messages(user):
    request = RequestFactory().get('/admin/')
    request.user = user
    request.session = {}
    setattr(request, '_messages', FallbackStorage(request))
    return request


@pytest.mark.django_db
def test_password_code_admin_disables_add_permission():
    """Password codes cannot be manually added through the admin."""
    admin = PasswordCodeAdmin(PasswordCode, admin_site)
    request = RequestFactory().get('/admin/')

    assert admin.has_add_permission(request) is False


@pytest.mark.django_db
def test_blog_admin_delete_queryset_removes_objects():
    """The blog admin bulk deletion removes selected blog records."""
    library = Library.objects.create(title='Blog Library')
    blog = Blog.objects.create(
        title='Test Blog',
        description='Desc',
        category='Cat',
        image=library,
    )

    admin = BlogAdmin(Blog, admin_site)
    admin.delete_queryset(RequestFactory().get('/admin/'), Blog.objects.filter(id=blog.id))

    assert Blog.objects.count() == 0


@pytest.mark.django_db
def test_product_admin_delete_queryset_removes_gallery():
    """Verifies ProductAdmin.delete_queryset removes the product and its associated gallery library."""
    library = Library.objects.create(title='Product Library')
    product = Product.objects.create(
        title='Test Product',
        category='Cat',
        sub_category='Sub',
        description='Desc',
        price=50,
        gallery=library,
    )

    admin = ProductAdmin(Product, admin_site)
    admin.delete_queryset(RequestFactory().get('/admin/'), Product.objects.filter(id=product.id))

    assert Product.objects.count() == 0
    assert Library.objects.filter(id=library.id).count() == 0


@pytest.mark.django_db
def test_sale_admin_delete_queryset_and_total():
    """Verifies SaleAdmin computes total products correctly and deletes the sale with its sold products."""
    library = Library.objects.create(title='Sale Library')
    product = Product.objects.create(
        title='Test Product',
        category='Cat',
        sub_category='Sub',
        description='Desc',
        price=50,
        gallery=library,
    )
    sold_product = SoldProduct.objects.create(product=product, quantity=2)
    sale = Sale.objects.create(
        email='buyer@example.com',
        address='Addr',
        city='City',
        state='State',
        postal_code='12345',
    )
    sale.sold_products.add(sold_product)

    admin = SaleAdmin(Sale, admin_site)

    assert admin.get_total_products(sale) == 1

    admin.delete_queryset(RequestFactory().get('/admin/'), Sale.objects.filter(id=sale.id))

    assert Sale.objects.count() == 0
    assert SoldProduct.objects.count() == 0


@pytest.mark.django_db
def test_admin_site_custom_sections():
    """Verifies the custom admin site exposes all required model sections in the app list."""
    User.objects.create_superuser(email='admin@example.com', password='pass1234')
    request = RequestFactory().get('/admin/')
    request.user = User.objects.get(email='admin@example.com')

    app_list = admin_site.get_app_list(request)

    object_names = {model['object_name'] for section in app_list for model in section['models']}

    assert {'User', 'PasswordCode', 'Blog', 'Product', 'Sale', 'SoldProduct'}.issubset(object_names)


@pytest.mark.django_db
def test_user_admin_login_as_link_renders_admin_url():
    """The impersonation link points to the target user's admin login action."""
    user = User.objects.create_user(email='target@example.com', password='pass1234')
    admin = BaseFeatureUserAdmin(User, admin_site)

    html = admin.login_as_link(user)

    assert 'Login as this user' in html
    assert f'/admin/base_feature_app/user/{user.id}/login_as/' in html


@pytest.mark.django_db
def test_user_admin_login_as_redirects_to_frontend(settings):
    """Successful admin impersonation redirects to the frontend with a token."""
    factory = RequestFactory()
    admin_user = User.objects.create_superuser(email='admin@example.com', password='pass1234')
    target_user = User.objects.create_user(email='target@example.com', password='pass1234')
    request = factory.get('/admin/')
    request.user = admin_user
    settings.FRONTEND_URL = 'http://localhost:3000'

    admin = BaseFeatureUserAdmin(User, admin_site)
    response = admin.login_as_user_view(request, target_user.id)

    assert response.status_code == 302
    assert response['Location'].startswith('http://localhost:3000/admin-login?')
    assert 'access=' in response['Location']
    assert 'refresh=' in response['Location']
    assert 'redirect=%2F' in response['Location']


@pytest.mark.django_db
def test_user_admin_login_as_requires_active_superuser():
    """Admin impersonation requires an active superuser operator."""
    factory = RequestFactory()
    regular_user = User.objects.create_user(email='user@example.com', password='pass1234')
    target_user = User.objects.create_user(email='target@example.com', password='pass1234')
    request = factory.get('/admin/')
    request.user = regular_user

    admin = BaseFeatureUserAdmin(User, admin_site)

    with pytest.raises(PermissionDenied) as exc_info:
        admin.login_as_user_view(request, target_user.id)

    assert exc_info.type is PermissionDenied


@pytest.mark.django_db
@pytest.mark.parametrize('build_target', [
    pytest.param(
        lambda: User.objects.create_superuser(email='target@example.com', password='pass1234'),
        id='superuser',
    ),
    pytest.param(
        lambda: User.objects.create_user(
            email='target@example.com', password='pass1234', is_active=False,
        ),
        id='inactive',
    ),
])
def test_user_admin_login_as_blocks_ineligible_target(build_target):
    """Admin impersonation rejects an ineligible target user."""
    admin_user = User.objects.create_superuser(email='admin@example.com', password='pass1234')
    target_user = build_target()
    request = _request_with_messages(admin_user)

    admin = BaseFeatureUserAdmin(User, admin_site)
    response = admin.login_as_user_view(request, target_user.id)

    assert response.status_code == 302
    assert 'access=' not in response['Location']
    assert f'/user/{target_user.id}/change/' in response['Location']


@pytest.mark.django_db
def test_media_admin_delete_model_preserves_other_owner(library_owners):
    """Individual admin deletion preserves the other owner's media."""
    model, admin, library, attachment, deleted, survivor, _ = library_owners
    deleted_id = deleted.pk

    admin.delete_model(RequestFactory().post('/admin/'), deleted)

    assert not model.objects.filter(pk=deleted_id).exists()
    assert model.objects.filter(pk=survivor.pk).exists()
    assert Library.objects.filter(pk=library.pk).exists()
    assert Attachment.objects.filter(pk=attachment.pk, library=library).exists()
    assert attachment.file.storage.exists(attachment.file.name)


@pytest.mark.django_db
def test_media_admin_delete_queryset_preserves_unselected_owner(library_owners):
    """Bulk admin deletion keeps media owned by an unselected third record."""
    model, admin, library, attachment, first, second, create_owner = library_owners
    survivor = create_owner(library, 'Unselected')
    selected_ids = [first.pk, second.pk]

    admin.delete_queryset(RequestFactory().post('/admin/'), model.objects.filter(pk__in=selected_ids))

    assert not model.objects.filter(pk__in=selected_ids).exists()
    assert model.objects.filter(pk=survivor.pk).exists()
    assert Library.objects.filter(pk=library.pk).exists()
    assert Attachment.objects.filter(pk=attachment.pk, library=library).exists()
    assert attachment.file.storage.exists(attachment.file.name)


@pytest.mark.django_db
def test_media_admin_delete_queryset_cleans_last_owners(library_owners, django_capture_on_commit_callbacks):
    """Bulk admin deletion removes media after the last selected owners' commit."""
    model, admin, library, attachment, first, second, _ = library_owners
    selected_ids = [first.pk, second.pk]

    with django_capture_on_commit_callbacks(execute=True):
        admin.delete_queryset(RequestFactory().post('/admin/'), model.objects.filter(pk__in=selected_ids))
        assert attachment.file.storage.exists(attachment.file.name)

    assert not model.objects.filter(pk__in=selected_ids).exists()
    assert not Library.objects.filter(pk=library.pk).exists()
    assert not Attachment.objects.filter(pk=attachment.pk).exists()
    assert not attachment.file.storage.exists(attachment.file.name)


@pytest.mark.django_db
def test_sale_admin_delete_model_preserves_other_owner(sale_owners):
    """Individual admin deletion preserves a line in a surviving sale."""
    admin, line, deleted, survivor = sale_owners
    deleted_id = deleted.pk

    admin.delete_model(RequestFactory().post('/admin/'), deleted)

    assert not Sale.objects.filter(pk=deleted_id).exists()
    assert Sale.objects.filter(pk=survivor.pk).exists()
    assert list(survivor.sold_products.values_list('pk', flat=True)) == [line.pk]


@pytest.mark.django_db
def test_sale_admin_delete_queryset_preserves_unselected_owner(sale_owners):
    """Bulk admin deletion preserves the line of an unselected third sale."""
    admin, line, first, second = sale_owners
    survivor = Sale.objects.create(email='third@example.com', address='A', city='C', state='S', postal_code='1')
    survivor.sold_products.add(line)
    selected_ids = [first.pk, second.pk]

    admin.delete_queryset(RequestFactory().post('/admin/'), Sale.objects.filter(pk__in=selected_ids))

    assert not Sale.objects.filter(pk__in=selected_ids).exists()
    assert Sale.objects.filter(pk=survivor.pk).exists()
    assert list(survivor.sold_products.values_list('pk', flat=True)) == [line.pk]


@pytest.mark.django_db
def test_sale_admin_delete_queryset_cleans_last_owners(sale_owners):
    """Bulk admin deletion cleans a line after its last selected sales."""
    admin, line, first, second = sale_owners
    selected_ids = [first.pk, second.pk]

    admin.delete_queryset(RequestFactory().post('/admin/'), Sale.objects.filter(pk__in=selected_ids))

    assert not Sale.objects.filter(pk__in=selected_ids).exists()
    assert not SoldProduct.objects.filter(pk=line.pk).exists()
