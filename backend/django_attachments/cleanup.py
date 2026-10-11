"""Clean attachment media only after its database change has committed."""

import logging
import os
from copy import copy
from functools import partial

from django.core.files.storage import storages
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save, pre_save
from easy_thumbnails.conf import settings
from easy_thumbnails.files import get_thumbnailer

logger = logging.getLogger('django.db.models')


def _schedule_cleanup(sender, field_name, file_instance, using, operation):
    """Capture the old descriptor independently of subsequent instance changes."""
    if file_instance.name:
        transaction.on_commit(
            partial(_clean_unreferenced_file, sender, field_name, copy(file_instance), using, operation),
            using=using,
        )


def _clean_unreferenced_file(sender, field_name, file_instance, using, operation):
    """Preserve confirmed references and contain failures after the commit."""
    # References on this alias are protected; concurrent reattachment and shared
    # storage across database aliases are outside this cleanup's guarantees.
    try:
        if sender.objects.using(using).filter(**{field_name: file_instance.name}).exists():
            return
        delete_file(file_instance)
    except Exception as exc:  # noqa: BLE001 -- Post-commit failures must not expose storage details or undo success.
        logger.error('Attachment cleanup failed: operation=%s error_type=%s', operation, type(exc).__name__)


def delete_files(sender, instance, using, **kwargs):
    """Defer deleted attachments' files until this connection commits."""
    for field in instance._meta.fields:
        if isinstance(field, models.FileField):
            _schedule_cleanup(sender, field.name, getattr(instance, field.name), using, 'delete')


def delete_old_files(sender, instance, using, raw=False, update_fields=None, **kwargs):
    """Capture replaced files before saving without performing side effects."""
    instance._attachment_old_files = {}
    if raw or not instance.pk:
        return
    try:
        old_instance = sender.objects.using(using).get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    for field in instance._meta.fields:
        if isinstance(field, models.FileField) and (update_fields is None or field.name in update_fields):
            old_file = getattr(old_instance, field.name)
            if old_file != getattr(instance, field.name):
                instance._attachment_old_files[field.name] = copy(old_file)


def delete_replaced_files(sender, instance, using, raw=False, **kwargs):
    """Schedule captured replacements only after a successful database save."""
    old_files = instance.__dict__.pop('_attachment_old_files', {})
    if raw:
        return
    for field_name, old_file in old_files.items():
        _schedule_cleanup(sender, field_name, old_file, using, 'replace')


def delete_file(file_instance):
    """Delete an unreferenced original and its generated thumbnails."""
    thumbnailer = get_thumbnailer(file_instance)
    thumbnailer.thumbnail_storage = storages[settings.THUMBNAIL_DEFAULT_STORAGE]
    thumbnailer.delete_thumbnails()
    storage = file_instance.storage
    file_path = file_instance.path
    if storage.exists(file_instance.name):
        storage.delete(file_instance.name)
        remove_empty_directories(os.path.dirname(file_path))


def remove_empty_directories(path):
    """Recursively remove empty directories."""
    if not os.listdir(path):
        os.rmdir(path)
        parent_directory = os.path.dirname(path)
        if parent_directory != path:
            remove_empty_directories(parent_directory)


def register_cleaner_for_model(model_cls):
    """Register one commit-aware cleanup owner for the attachment model."""
    post_delete.connect(delete_files, sender=model_cls)
    pre_save.connect(delete_old_files, sender=model_cls)
    post_save.connect(delete_replaced_files, sender=model_cls)
