from django.db import models, router, transaction
from base_feature_app.models import Product

class SoldProduct(models.Model):
    """
    Model representing a product in the cart.
    """
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField()

    def __str__(self):
        return f'{self.product.title} (Qty: {self.quantity})'

class Sale(models.Model):
    """
    Model representing a sale.
    """
    email = models.EmailField()
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    sold_products = models.ManyToManyField(SoldProduct)

    def __str__(self):
        return self.email

    def delete(self, using=None, keep_parents=False):
        using = using or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            sold_product_ids = list(self.sold_products.using(using).values_list('pk', flat=True))
            super().delete(using=using, keep_parents=keep_parents)
            SoldProduct.objects.using(using).filter(
                pk__in=sold_product_ids,
                sale__isnull=True,
            ).delete()
