import pytest
from django_attachments.models import Library
from rest_framework.exceptions import ValidationError

from base_feature_app.models import Product, Sale, SoldProduct
from base_feature_app.serializers.sale import SaleSerializer


@pytest.mark.django_db
def test_sale_serializer_creates_sold_products():
    """Verifies SaleSerializer creates a Sale with linked SoldProduct records from the nested payload."""
    gallery = Library.objects.create(title='Gallery')
    product = Product.objects.create(
        title='P',
        category='C',
        sub_category='S',
        description='D',
        price=10,
        gallery=gallery,
    )

    payload = {
        'email': 'a@a.com',
        'address': 'A',
        'city': 'C',
        'state': 'S',
        'postal_code': '1',
        'sold_products': [{'product_id': product.id, 'quantity': 2}],
    }

    serializer = SaleSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors
    sale = serializer.save()

    assert sale.sold_products.count() == 1
    assert sale.sold_products.first().quantity == 2


@pytest.fixture
def sale_products(db):
    """Create two products with separate galleries for deletion after sale validation."""
    return tuple(
        Product.objects.create(
            title=f'Product {index}',
            category='C',
            sub_category='S',
            description='D',
            price=10,
            gallery=Library.objects.create(title=f'Gallery {index}'),
        )
        for index in range(2)
    )


@pytest.fixture
def sale_payload(sale_products):
    """Build a valid two-product sale payload for validation and rollback checks."""
    return {
        'email': 'customer@example.com',
        'address': 'A',
        'city': 'C',
        'state': 'S',
        'postal_code': '1',
        'sold_products': [
            {'product_id': product.pk, 'quantity': 2}
            for product in sale_products
        ],
    }


@pytest.mark.django_db
def test_sale_serializer_rejects_missing_product(sale_payload, sale_products):
    """Reject a missing product following a valid product before any sale writes."""
    sale_payload['sold_products'][1]['product_id'] = sale_products[1].pk + 1000
    serializer = SaleSerializer(data=sale_payload)

    is_valid = serializer.is_valid()

    assert is_valid is False
    assert 'product_id' in serializer.errors['sold_products'][1]
    assert Sale.objects.count() == 0
    assert SoldProduct.objects.count() == 0
    assert Sale.sold_products.through.objects.count() == 0


@pytest.mark.django_db
def test_sale_serializer_rolls_back_after_product_disappears(sale_payload, sale_products):
    """Roll back the first sale line when the second product disappears after validation."""
    serializer = SaleSerializer(data=sale_payload)
    assert serializer.is_valid(), serializer.errors
    sale_products[1].delete()

    with pytest.raises(ValidationError, match='products no longer exist'):
        serializer.save()

    assert Sale.objects.count() == 0
    assert SoldProduct.objects.count() == 0
    assert Sale.sold_products.through.objects.count() == 0
