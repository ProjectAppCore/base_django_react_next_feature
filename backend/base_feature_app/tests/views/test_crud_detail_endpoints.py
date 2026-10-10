"""Verify staff CRUD operations and detail endpoint error responses."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from django_attachments.models import Attachment, Library
from rest_framework import status

from base_feature_app.models import Blog, Product, Sale, SoldProduct


@pytest.fixture
def staff_user(db):
    """Create a staff account authorized to exercise protected endpoints."""
    User = get_user_model()
    user = User.objects.create_user(email='staff2@example.com', password='pass1234')
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    return user


def _create_blog():
    library = Library.objects.create(title='Blog Library')
    return Blog.objects.create(title='Blog', description='Desc', category='Cat', image=library)


def _create_product():
    gallery = Library.objects.create(title='Gallery')
    return Product.objects.create(
        title='Product',
        category='Cat',
        sub_category='Sub',
        description='Desc',
        price=10,
        gallery=gallery,
    )


def _create_sale():
    product = _create_product()
    sold = SoldProduct.objects.create(product=product, quantity=2)
    sale = Sale.objects.create(email='buyer@example.com', address='Addr', city='City', state='State', postal_code='123')
    sale.sold_products.add(sold)
    return sale


@pytest.fixture(params=[
    pytest.param(
        (Blog, 'blog-detail', 'blog_id', lambda library, title: Blog.objects.create(
            title=title, description='D', category='C', image=library,
        )),
        id='blog',
    ),
    pytest.param(
        (Product, 'product-detail', 'product_id', lambda library, title: Product.objects.create(
            title=title, description='D', category='C', sub_category='S', price=10, gallery=library,
        )),
        id='product',
    ),
])
def shared_media_endpoint(request, settings, tmp_path, db):
    """Create two API resources sharing a library with a real attachment."""
    settings.MEDIA_ROOT = str(tmp_path / 'media')
    model, route, id_field, create_owner = request.param
    library = Library.objects.create(title='Shared media')
    attachment = Attachment.objects.create(
        library=library, file=ContentFile(b'Shared content', name='shared.txt'), rank=0,
    )
    deleted = create_owner(library, 'Deleted')
    survivor = create_owner(library, 'Survivor')
    return model, reverse(route, kwargs={id_field: deleted.pk}), deleted.pk, survivor, library, attachment


@pytest.mark.django_db
def test_detail_delete_preserves_shared_media(api_client, staff_user, shared_media_endpoint):
    """A successful DELETE removes only the selected owner of shared media."""
    model, url, deleted_id, survivor, library, attachment = shared_media_endpoint
    api_client.force_authenticate(user=staff_user)

    response = api_client.delete(url)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not model.objects.filter(pk=deleted_id).exists()
    assert model.objects.filter(pk=survivor.pk).exists()
    assert Library.objects.filter(pk=library.pk).exists()
    assert Attachment.objects.filter(pk=attachment.pk, library=library).exists()
    assert attachment.file.storage.exists(attachment.file.name)


@pytest.mark.django_db
def test_blog_crud_list(api_client):
    """The staff blog list endpoint returns a successful response."""
    _create_blog()

    response = api_client.get(reverse('blogs'))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_blog_crud_create_success(api_client, staff_user):
    """Valid staff blog creation returns a created response."""
    library = Library.objects.create(title='Blog Library')
    api_client.force_authenticate(user=staff_user)

    response = api_client.post(
        reverse('blogs'),
        {'title': 'New', 'description': 'Desc', 'category': 'Cat', 'image': library.id},
        format='json',
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Blog.objects.filter(title='New').exists()


@pytest.mark.django_db
def test_blog_crud_create_invalid(api_client, staff_user):
    """Staff blog creation rejects an invalid request payload."""
    api_client.force_authenticate(user=staff_user)

    response = api_client.post(reverse('blogs'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_blog_detail_get_success(api_client):
    """Retrieving an existing blog detail returns a successful response."""
    blog = _create_blog()

    response = api_client.get(reverse('blog-detail', kwargs={'blog_id': blog.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['id'] == blog.id


@pytest.mark.django_db
def test_blog_detail_not_found(api_client):
    """Retrieving an unknown blog returns a not-found response."""
    response = api_client.get(reverse('blog-detail', kwargs={'blog_id': 999}))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_blog_detail_update_requires_staff(api_client):
    """Blog updates reject users without staff permissions."""
    blog = _create_blog()

    response = api_client.patch(
        reverse('blog-detail', kwargs={'blog_id': blog.id}),
        {'title': 'Updated'},
        format='json',
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_blog_detail_update_success(api_client, staff_user):
    """Valid staff blog updates return a successful response."""
    blog = _create_blog()
    api_client.force_authenticate(user=staff_user)

    response = api_client.patch(
        reverse('blog-detail', kwargs={'blog_id': blog.id}),
        {'title': 'Updated'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    blog.refresh_from_db()
    assert blog.title == 'Updated'


@pytest.mark.django_db
def test_blog_detail_update_invalid(api_client, staff_user):
    """Staff blog updates reject an invalid request payload."""
    blog = _create_blog()
    api_client.force_authenticate(user=staff_user)

    response = api_client.patch(
        reverse('blog-detail', kwargs={'blog_id': blog.id}),
        {'title': ''},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_blog_detail_delete(api_client, staff_user):
    """Staff blog deletion returns a successful deletion response."""
    blog = _create_blog()
    api_client.force_authenticate(user=staff_user)

    response = api_client.delete(reverse('blog-detail', kwargs={'blog_id': blog.id}))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert Blog.objects.count() == 0


@pytest.mark.django_db
def test_product_crud_list(api_client):
    """The staff product list endpoint returns a successful response."""
    _create_product()

    response = api_client.get(reverse('products'))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_product_crud_create_success(api_client, staff_user):
    """Verifies staff users can create a new product via the products endpoint with valid data."""
    gallery = Library.objects.create(title='Gallery')
    api_client.force_authenticate(user=staff_user)

    response = api_client.post(
        reverse('products'),
        {
            'title': 'New',
            'category': 'Cat',
            'sub_category': 'Sub',
            'description': 'Desc',
            'price': 25,
            'gallery': gallery.id,
        },
        format='json',
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Product.objects.filter(title='New').exists()


@pytest.mark.django_db
def test_product_crud_create_invalid(api_client, staff_user):
    """Staff product creation rejects an invalid request payload."""
    api_client.force_authenticate(user=staff_user)

    response = api_client.post(reverse('products'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_product_detail_get_success(api_client):
    """Retrieving an existing product detail returns a successful response."""
    product = _create_product()

    response = api_client.get(reverse('product-detail', kwargs={'product_id': product.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['id'] == product.id


@pytest.mark.django_db
def test_product_detail_not_found(api_client):
    """Retrieving an unknown product returns a not-found response."""
    response = api_client.get(reverse('product-detail', kwargs={'product_id': 999}))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_product_detail_update_requires_staff(api_client):
    """Product updates reject users without staff permissions."""
    product = _create_product()

    response = api_client.patch(
        reverse('product-detail', kwargs={'product_id': product.id}),
        {'title': 'Updated'},
        format='json',
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_product_detail_update_success(api_client, staff_user):
    """Valid staff product updates return a successful response."""
    product = _create_product()
    api_client.force_authenticate(user=staff_user)

    response = api_client.patch(
        reverse('product-detail', kwargs={'product_id': product.id}),
        {'title': 'Updated'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    product.refresh_from_db()
    assert product.title == 'Updated'


@pytest.mark.django_db
def test_product_detail_update_invalid(api_client, staff_user):
    """Staff product updates reject an invalid request payload."""
    product = _create_product()
    api_client.force_authenticate(user=staff_user)

    response = api_client.patch(
        reverse('product-detail', kwargs={'product_id': product.id}),
        {'title': ''},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_product_detail_delete(api_client, staff_user):
    """Staff product deletion returns a successful deletion response."""
    product = _create_product()
    api_client.force_authenticate(user=staff_user)

    response = api_client.delete(reverse('product-detail', kwargs={'product_id': product.id}))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert Product.objects.count() == 0


@pytest.mark.django_db
def test_user_crud_list_and_create(api_client, staff_user):
    """Verifies staff users can list existing users and create a new user via the user-list endpoint."""
    api_client.force_authenticate(user=staff_user)

    response = api_client.get(reverse('user-list'))
    assert response.status_code == status.HTTP_200_OK

    response = api_client.post(
        reverse('user-list'),
        {'email': 'newuser@example.com', 'password': 'pass1234', 'role': 'customer'},
        format='json',
    )

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_user_crud_create_invalid(api_client, staff_user):
    """Staff user creation rejects an invalid request payload."""
    api_client.force_authenticate(user=staff_user)

    response = api_client.post(reverse('user-list'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_user_detail_get_update_delete(api_client, staff_user):
    """Verifies staff users can retrieve, partially update, and delete a user via the user-detail endpoint."""
    User = get_user_model()
    target = User.objects.create_user(email='target@example.com', password='pass1234')
    api_client.force_authenticate(user=staff_user)

    response = api_client.get(reverse('user-detail', kwargs={'user_id': target.id}))
    assert response.status_code == status.HTTP_200_OK

    response = api_client.patch(
        reverse('user-detail', kwargs={'user_id': target.id}),
        {'first_name': 'Updated'},
        format='json',
    )
    assert response.status_code == status.HTTP_200_OK

    response = api_client.delete(reverse('user-detail', kwargs={'user_id': target.id}))
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_user_detail_not_found(api_client, staff_user):
    """Retrieving an unknown user returns a not-found response."""
    api_client.force_authenticate(user=staff_user)

    response = api_client.get(reverse('user-detail', kwargs={'user_id': 999}))

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_user_detail_update_invalid(api_client, staff_user):
    """Staff user updates reject an invalid request payload."""
    User = get_user_model()
    target = User.objects.create_user(email='invalid@example.com', password='pass1234')
    api_client.force_authenticate(user=staff_user)

    response = api_client.put(
        reverse('user-detail', kwargs={'user_id': target.id}),
        {},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_sale_list_and_detail(api_client, staff_user):
    """Staff users can retrieve sale list and detail responses."""
    sale = _create_sale()
    api_client.force_authenticate(user=staff_user)

    response = api_client.get(reverse('sale-list'))
    assert response.status_code == status.HTTP_200_OK

    response = api_client.get(reverse('sale-detail', kwargs={'sale_id': sale.id}))
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_sale_detail_not_found(api_client, staff_user):
    """Retrieving an unknown sale returns a not-found response."""
    api_client.force_authenticate(user=staff_user)

    response = api_client.get(reverse('sale-detail', kwargs={'sale_id': 999}))

    assert response.status_code == status.HTTP_404_NOT_FOUND
