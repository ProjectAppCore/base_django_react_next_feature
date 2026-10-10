import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from base_feature_app.models import Product, Sale, SoldProduct
from django_attachments.models import Library


@pytest.fixture
def target_user(db):
    return get_user_model().objects.create_user(
        email='target@example.com', password='pass1234', phone='5551234',
    )


@pytest.fixture
def customer_client(api_client, db, settings):
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
    return Library.objects.create(title='Permission Test Gallery')


@pytest.fixture
def product(gallery):
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
    response = api_client.get(reverse('sale-detail', kwargs={'sale_id': sale.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Authentication required.'}


@pytest.mark.django_db
def test_user_detail_requires_staff(api_client):
    User = get_user_model()
    user = User.objects.create_user(email='target@example.com', password='pass1234')

    response = api_client.get(reverse('user-detail', kwargs={'user_id': user.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Authentication required.'}


@pytest.mark.django_db
def test_sale_detail_rejects_customer_jwt(customer_client, sale):
    response = customer_client.get(reverse('sale-detail', kwargs={'sale_id': sale.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Admin access required.'}


@pytest.mark.django_db
def test_user_detail_rejects_customer_jwt(customer_client, target_user):
    response = customer_client.get(reverse('user-detail', kwargs={'user_id': target_user.id}))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Admin access required.'}


@pytest.mark.django_db
@pytest.mark.parametrize(('route', 'lookup'), [
    ('user-detail', {'user_id': 999999}), ('sale-detail', {'sale_id': 999999}),
])
def test_admin_detail_hides_missing_object_from_customer(customer_client, route, lookup):
    response = customer_client.get(reverse(route, kwargs=lookup))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Admin access required.'}


@pytest.mark.django_db
def test_sale_detail_returns_address_for_staff(staff_client, sale):
    response = staff_client.get(reverse('sale-detail', kwargs={'sale_id': sale.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data['email'] == sale.email
    assert response.data['address'] == sale.address


@pytest.mark.django_db
def test_user_detail_returns_phone_for_staff(staff_client, target_user):
    response = staff_client.get(reverse('user-detail', kwargs={'user_id': target_user.id}))

    assert response.status_code == status.HTTP_200_OK
    assert response.data['phone'] == target_user.phone


@pytest.mark.django_db
@pytest.mark.parametrize(('route', 'lookup'), [
    ('user-detail', {'user_id': 999999}), ('sale-detail', {'sale_id': 999999}),
])
def test_admin_detail_returns_not_found_to_staff(staff_client, route, lookup):
    response = staff_client.get(reverse(route, kwargs=lookup))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data == {'detail': 'Not found.'}


@pytest.mark.django_db
@pytest.mark.parametrize(('route', 'lookup'), [
    ('user-detail', {'user_id': 999999}), ('sale-detail', {'sale_id': 999999}),
])
def test_admin_detail_rejects_invalid_jwt(api_client, route, lookup):
    api_client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')

    response = api_client.get(reverse(route, kwargs=lookup))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_create_sale_returns_201_with_valid_payload(api_client, product):
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
