import pytest
from django_attachments.models import Library

from base_feature_app.models import Product, Sale, SoldProduct


@pytest.fixture
def sale_product(db):
    """Create a product for sale deletion scenarios."""
    library = Library.objects.create(title='Gallery')
    return Product.objects.create(
        title='Product', category='C', sub_category='S', description='D', price=10, gallery=library,
    )


def _create_sale(email):
    """Create a sale without lines for the ownership scenario."""
    return Sale.objects.create(email=email, address='A', city='C', state='S', postal_code='1')


@pytest.mark.django_db
def test_sold_product_str_includes_title_and_quantity():
    gallery = Library.objects.create(title='Gallery')
    product = Product.objects.create(
        title='Widget',
        category='Cat',
        sub_category='Sub',
        description='Desc',
        price=10,
        gallery=gallery,
    )
    sold = SoldProduct.objects.create(product=product, quantity=3)

    assert str(sold) == f'{product.title} (Qty: {sold.quantity})'


@pytest.mark.django_db
def test_sale_str_returns_email():
    """Verifies that the string representation of a Sale returns its email address."""
    gallery = Library.objects.create(title='Gallery2')
    product = Product.objects.create(
        title='Widget2',
        category='Cat',
        sub_category='Sub',
        description='Desc',
        price=10,
        gallery=gallery,
    )
    sold = SoldProduct.objects.create(product=product, quantity=1)
    sale = Sale.objects.create(
        email='buyer@example.com',
        address='Addr',
        city='City',
        state='State',
        postal_code='123',
    )
    sale.sold_products.add(sold)

    assert str(sale) == sale.email


@pytest.mark.django_db
def test_sale_delete_removes_sold_products():
    """Verifies that deleting a Sale also removes all associated SoldProduct records."""
    gallery = Library.objects.create(title='Gallery')
    product = Product.objects.create(
        title='P',
        category='C',
        sub_category='S',
        description='D',
        price=10,
        gallery=gallery,
    )

    sold = SoldProduct.objects.create(product=product, quantity=1)
    sale = Sale.objects.create(email='a@a.com', address='A', city='C', state='S', postal_code='1')
    sale.sold_products.add(sold)

    sold_id = sold.id
    sale.delete()

    assert not SoldProduct.objects.filter(id=sold_id).exists()


@pytest.mark.django_db
def test_sale_delete_preserves_shared_line(sale_product):
    """Deleting one sale preserves the line still linked to another sale."""
    line = SoldProduct.objects.create(product=sale_product, quantity=2)
    deleted = _create_sale('deleted@example.com')
    deleted_id = deleted.pk
    survivor = _create_sale('survivor@example.com')
    deleted.sold_products.add(line)
    survivor.sold_products.add(line)

    result = deleted.delete(using='default')

    assert result is None
    assert not Sale.objects.filter(pk=deleted_id).exists()
    assert Sale.objects.filter(pk=survivor.pk).exists()
    assert SoldProduct.objects.filter(pk=line.pk, product=sale_product, quantity=2).exists()
    assert list(survivor.sold_products.values_list('pk', flat=True)) == [line.pk]


@pytest.mark.django_db
def test_sale_delete_removes_only_exclusive_line(sale_product):
    """Shared lines survive cleanup alongside an exclusive line."""
    shared = SoldProduct.objects.create(product=sale_product, quantity=2)
    exclusive = SoldProduct.objects.create(product=sale_product, quantity=1)
    deleted = _create_sale('deleted@example.com')
    survivor = _create_sale('survivor@example.com')
    deleted.sold_products.add(shared, exclusive)
    survivor.sold_products.add(shared)

    deleted.delete()

    assert not SoldProduct.objects.filter(pk=exclusive.pk).exists()
    assert list(survivor.sold_products.values_list('pk', flat=True)) == [shared.pk]


@pytest.mark.django_db
def test_sale_delete_cleans_line_after_last_owner(sale_product):
    """Removing the final sale cleans its formerly shared line."""
    line = SoldProduct.objects.create(product=sale_product, quantity=2)
    first = _create_sale('first@example.com')
    last = _create_sale('last@example.com')
    first.sold_products.add(line)
    last.sold_products.add(line)
    first.delete()

    last.delete()

    assert not SoldProduct.objects.filter(pk=line.pk).exists()
