import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status


@pytest.fixture
def staff_user(db):
    User = get_user_model()
    user = User.objects.create_user(email='staff@example.com', password='pass1234')
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    return user


@pytest.fixture
def staff_client(api_client, staff_user, settings):
    """Authenticate staff through the real sign-in endpoint."""
    settings.RECAPTCHA_SECRET_KEY = ''
    response = api_client.post(reverse('sign_in'), {
        'email': staff_user.email, 'password': 'pass1234',
    }, format='json')
    assert response.status_code == status.HTTP_200_OK
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api_client


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


@pytest.mark.django_db
def test_users_list_requires_staff(api_client):
    url = reverse('user-list')
    response = api_client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Authentication required.'}


@pytest.mark.django_db
def test_users_list_success_for_staff(staff_client, staff_user):
    url = reverse('user-list')
    response = staff_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data[0]['email'] == staff_user.email


@pytest.mark.django_db
def test_products_create_requires_staff(api_client):
    url = reverse('products')
    response = api_client.post(url, {}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_blogs_create_requires_staff(api_client):
    url = reverse('blogs')
    response = api_client.post(url, {}, format='json')
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_sales_list_requires_staff(api_client):
    url = reverse('sale-list')
    response = api_client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Authentication required.'}


@pytest.mark.django_db
@pytest.mark.parametrize('route', ['user-list', 'sale-list'])
def test_admin_list_rejects_customer_jwt(customer_client, route):
    """Deny administrative lists to a non-staff JWT holder."""
    response = customer_client.get(reverse(route))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data == {'detail': 'Admin access required.'}


@pytest.mark.django_db
@pytest.mark.parametrize('route', ['user-list', 'sale-list'])
def test_admin_list_rejects_invalid_jwt(api_client, route):
    """Reject malformed JWTs before exposing administrative lists."""
    api_client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')

    response = api_client.get(reverse(route))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_sales_list_returns_sale_for_staff(staff_client):
    """Return the existing sale list payload to authenticated staff."""
    from base_feature_app.models import Sale

    sale = Sale.objects.create(
        email='buyer@example.com', address='Address', city='City', state='State', postal_code='123',
    )

    response = staff_client.get(reverse('sale-list'))

    assert response.status_code == status.HTTP_200_OK
    assert response.data == [{
        'id': sale.id, 'email': sale.email, 'city': sale.city,
        'state': sale.state, 'postal_code': sale.postal_code,
    }]
