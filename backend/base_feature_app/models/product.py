from django.db import models, router, transaction
from django_attachments.fields import GalleryField

from ._cleanup import _delete_orphan_library

class Product(models.Model):
    """
    Product model.

    :ivar category: category product.
    :vartype category: str
    :ivar sub_category: subcategory product.
    :vartype sub_category: str
    :ivar title: title product.
    :vartype title: str
    :ivar description: description product.
    :vartype description: str
    :ivar price: price of the product.
    :vartype price: int
    :ivar gallery: gallery of images associated with the product.
    :vartype gallery: Gallery
    :ivar categoria: category of the product in Spanish.
    """

    title = models.CharField(max_length=40)
    category = models.CharField(max_length=40)
    sub_category = models.CharField(max_length=40)    
    description = models.TextField()

    price = models.IntegerField()
    gallery = GalleryField(related_name='products_with_attachment', on_delete=models.CASCADE)

    def __str__(self):
        return self.title

    def delete(self, using=None, keep_parents=False):
        using = using or router.db_for_write(type(self), instance=self)
        library_id = self.gallery_id
        with transaction.atomic(using=using):
            super().delete(using=using, keep_parents=keep_parents)
            _delete_orphan_library(library_id, using=using)
