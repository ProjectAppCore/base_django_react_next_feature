import pytest
from django.urls import reverse
from django_attachments.models import Library
from rest_framework import status

from base_feature_app.models import Blog, Product, Sale, SoldProduct


@pytest.fixture
def library(db):
    return Library.objects.create(title='Test Library')


@pytest.fixture
def product(db, library):
    return Product.objects.create(
        title='Test Product',
        category='Test Category',
        sub_category='Test Sub',
        description='Test Description',
        price=100,
        gallery=library,
    )


@pytest.fixture
def blog(db, library):
    return Blog.objects.create(
        title='Test Blog',
        description='Test Description',
        category='Test Category',
        image=library,
    )


@pytest.mark.django_db
def test_product_list_success(api_client, product):
    url = reverse('product-list')
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


@pytest.mark.django_db
def test_blog_list_success(api_client, blog):
    url = reverse('blog-list')
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


@pytest.mark.django_db
def test_create_sale_validation_error(api_client):
    url = reverse('create-sale')
    response = api_client.post(url, {}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.fixture
def sale_payload(product):
    """Build checkout data with a valid product followed by a missing product."""
    return {
        'email': 'customer@example.com',
        'address': '123 Main Street',
        'city': 'New York',
        'state': 'NY',
        'postal_code': '10001',
        'sold_products': [
            {'product_id': product.pk, 'quantity': 2},
            {'product_id': product.pk + 1000, 'quantity': 1},
        ],
    }


@pytest.mark.django_db
def test_create_sale_rejects_missing_product(api_client, sale_payload):
    """Reject a valid product followed by a missing product without persisting a sale."""
    url = reverse('create-sale')

    response = api_client.post(url, sale_payload, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'product_id' in response.data['sold_products'][1]
    assert Sale.objects.count() == 0
    assert SoldProduct.objects.count() == 0
    assert Sale.sold_products.through.objects.count() == 0


@pytest.mark.django_db
def test_create_sale_repeated_rejection_leaves_no_sale(api_client, sale_payload):
    """Keep sale storage empty when the same invalid checkout is submitted twice."""
    url = reverse('create-sale')

    first_response = api_client.post(url, sale_payload, format='json')
    second_response = api_client.post(url, sale_payload, format='json')

    assert [first_response.status_code, second_response.status_code] == [400, 400]
    assert Sale.objects.count() == 0
    assert SoldProduct.objects.count() == 0
    assert Sale.sold_products.through.objects.count() == 0


@pytest.mark.django_db
def test_create_sale_succeeds_after_rejected_attempt(api_client, sale_payload, product):
    """Persist one complete sale after the shopper removes a missing product."""
    url = reverse('create-sale')
    rejected_response = api_client.post(url, sale_payload, format='json')
    assert rejected_response.status_code == status.HTTP_400_BAD_REQUEST
    sale_payload['sold_products'].pop()

    response = api_client.post(url, sale_payload, format='json')

    assert response.status_code == status.HTTP_201_CREATED
    assert Sale.objects.count() == 1
    assert response.data['id'] == Sale.objects.get().pk
    assert SoldProduct.objects.count() == 1
    assert Sale.sold_products.through.objects.count() == 1
    sold_product = SoldProduct.objects.get()
    assert sold_product.product_id == product.pk
    assert sold_product.quantity == 2
