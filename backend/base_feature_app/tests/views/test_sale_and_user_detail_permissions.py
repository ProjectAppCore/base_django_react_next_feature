"""Verify sale creation and protected detail endpoint permissions."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django_attachments.models import Library
from rest_framework import status

from base_feature_app.models import Product, Sale, SoldProduct


@pytest.fixture
def target_user(db):
    """Create a user whose phone can be retrieved by staff."""
    return get_user_model().objects.create_user(
        email='target@example.com', password='pass1234', phone='5551234',
    )


@pytest.fixture
def customer_client(api_client, db, settings):
    """Authenticate a non-staff user carrying an admin role label."""
    settings.RECAPTCHA_SECRET_KEY = ''
    get_user_model().objects.create_user(
        email='customer@example.com', password='pass1234', role='admin', is_staff=False,
    )
    response = api_client.post(reverse('sign_in'), {
        'email': 'customer@example.com', 'password': 'pass1234',
    }, format='json')
    assert response.status_code == status.HTTP_200_OK
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api_client


@pytest.fixture
def staff_client(api_client, db, settings):
    """Authenticate staff carrying a customer role label."""
    settings.RECAPTCHA_SECRET_KEY = ''
    get_user_model().objects.create_user(
        email='staff@example.com', password='pass1234', role='customer', is_staff=True,
    )
    response = api_client.post(reverse('sign_in'), {
        'email': 'staff@example.com', 'password': 'pass1234',
    }, format='json')
    assert response.status_code == status.HTTP_200_OK
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api_client


@pytest.fixture
def gallery(db):
    """Create an image gallery for the sale's product fixture."""
    return Library.objects.create(title='Permission Test Gallery')


@pytest.fixture
def product(gallery):
    """Create a product used by the endpoint response tests."""
    return Product.objects.create(
        title='Permission Product',
        category='Cat',
        sub_category='Sub',
        description='Desc',
        price=10,
        gallery=gallery,
    )


@pytest.fixture
def sale(product):
    """Create a sale for protected sale-detail requests."""
    sold = SoldProduct.objects.create(product=product, quantity=2)
    s = Sale.objects.create(
        email='buyer@example.com',
        address='Addr',
        city='City',
        state='State',
        postal_code='123',
    )
    s.sold_products.add(sold)
    return s


@pytest.mark.django_db
def test_sale_detail_requires_staff(api_client, sale):
    """Sale detail access rejects users without staff permissions."""
    response = api_client.get(reverse('sale-detail', kwargs={'sale_id': sale.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Authentication required.'}


@pytest.mark.django_db
def test_user_detail_requires_staff(api_client):
    """User detail access rejects users without staff permissions."""
    User = get_user_model()
    user = User.objects.create_user(email='target@example.com', password='pass1234')

    response = api_client.get(reverse('user-detail', kwargs={'user_id': user.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Authentication required.'}


@pytest.mark.django_db
def test_sale_detail_rejects_customer_jwt(customer_client, sale):
    """Deny an existing sale detail to a non-staff JWT holder."""
    response = customer_client.get(reverse('sale-detail', kwargs={'sale_id': sale.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Admin access required.'}


@pytest.mark.django_db
def test_user_detail_rejects_customer_jwt(customer_client, target_user):
    """Deny an existing user detail to a non-staff JWT holder."""
    response = customer_client.get(reverse('user-detail', kwargs={'user_id': target_user.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Admin access required.'}


@pytest.mark.django_db
@pytest.mark.parametrize(('route', 'lookup'), [
    ('user-detail', {'user_id': 999999}), ('sale-detail', {'sale_id': 999999}),
])
def test_admin_detail_hides_missing_object_from_customer(customer_client, route, lookup):
    """Deny non-staff access before revealing object existence."""
    response = customer_client.get(reverse(route, kwargs=lookup))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Admin access required.'}


@pytest.mark.django_db
def test_sale_detail_returns_address_for_staff(staff_client, sale):
    """Return an existing sale address to authenticated staff."""
    response = staff_client.get(reverse('sale-detail', kwargs={'sale_id': sale.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data['email'] == sale.email
    assert response.data['address'] == sale.address


@pytest.mark.django_db
def test_user_detail_returns_phone_for_staff(staff_client, target_user):
    """Return an existing user phone to authenticated staff."""
    response = staff_client.get(reverse('user-detail', kwargs={'user_id': target_user.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data['phone'] == target_user.phone


@pytest.mark.django_db
@pytest.mark.parametrize(('route', 'lookup'), [
    ('user-detail', {'user_id': 999999}), ('sale-detail', {'sale_id': 999999}),
])
def test_admin_detail_returns_not_found_to_staff(staff_client, route, lookup):
    """Report a missing administrative object to authenticated staff."""
    response = staff_client.get(reverse(route, kwargs=lookup))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data == {'detail': 'Not found.'}


@pytest.mark.django_db
@pytest.mark.parametrize(('route', 'lookup'), [
    ('user-detail', {'user_id': 999999}), ('sale-detail', {'sale_id': 999999}),
])
def test_admin_detail_rejects_invalid_jwt(api_client, route, lookup):
    """Reject malformed JWTs before looking up administrative objects."""
    api_client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')

    response = api_client.get(reverse(route, kwargs=lookup))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_create_sale_returns_201_with_valid_payload(api_client, product):
    """A valid public sale request returns a created response."""
    payload = {
        'email': 'buyer@example.com',
        'address': 'Addr',
        'city': 'City',
        'state': 'State',
        'postal_code': '123',
        'sold_products': [{'product_id': product.id, 'quantity': 1}],
    }

    response = api_client.post(reverse('create-sale'), payload, format='json')

    assert response.status_code == status.HTTP_201_CREATED
    assert Sale.objects.count() == 1
