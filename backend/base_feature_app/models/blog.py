from django.db import models, router, transaction
from django_attachments.fields import SingleImageField

from ._cleanup import _delete_orphan_library

class Blog(models.Model):
    """
    Blog model.

    :ivar title: title blog.
    :vartype title: str
    :ivar description: description blog.
    :vartype description: str
    :ivar category: category blog.
    :vartype category: str
    :ivar image: image by blog.
    :vartype image: Image
    """

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=40)
    image = SingleImageField(related_name='blog_image', on_delete=models.CASCADE)

    def __str__(self):
        return self.title
    
    def delete(self, using=None, keep_parents=False):
        using = using or router.db_for_write(type(self), instance=self)
        library_id = self.image_id
        with transaction.atomic(using=using):
            super().delete(using=using, keep_parents=keep_parents)
            _delete_orphan_library(library_id, using=using)
