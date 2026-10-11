"""Verify attachment media cleanup against committed database state."""

import io
import logging
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.files.base import ContentFile
from django.db import IntegrityError, connections, transaction
from django_attachments.models import Attachment, Library
from easy_thumbnails.files import get_thumbnailer
from PIL import Image

pytestmark = pytest.mark.django_db(transaction=True)


def _image(name='original.png'):
    """Build an image entirely from synthetic bytes."""
    output = io.BytesIO()
    Image.new('RGB', (8, 8), color='red').save(output, format='PNG')
    return ContentFile(output.getvalue(), name=name)


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    """Keep original images and thumbnails inside the test's temporary storage."""
    settings.MEDIA_ROOT = str(tmp_path / 'media')


@pytest.fixture
def media_record():
    """Persist one attachment with a generated thumbnail and its original bytes."""
    library = Library.objects.create(title='Cleanup test')
    attachment = Attachment.objects.create(library=library, file=_image(), rank=0)
    thumbnail = get_thumbnailer(attachment.file).get_thumbnail({'size': (2, 2)})
    return SimpleNamespace(
        attachment=attachment, pk=attachment.pk, name=attachment.file.name,
        original=Path(attachment.file.path), thumbnail=Path(thumbnail.path),
        content=Path(attachment.file.path).read_bytes(),
    )


def _delete(attachment):
    attachment.delete()


def _replace(attachment):
    attachment.file = _image('replacement.png')
    attachment.save(update_fields=['file'])


@pytest.mark.parametrize('operation', [_delete, _replace], ids=['delete', 'replace'])
def test_rollback_preserves_referenced_media(media_record, operation):
    """A database rollback keeps the original image and its thumbnail readable."""
    with transaction.atomic():
        operation(media_record.attachment)
        transaction.set_rollback(True)

    assert Attachment.objects.get(pk=media_record.pk).file.name == media_record.name
    assert media_record.original.read_bytes() == media_record.content
    assert media_record.thumbnail.exists()


@pytest.mark.parametrize('operation', [_delete, _replace], ids=['delete', 'replace'])
def test_commit_removes_obsolete_media(media_record, operation):
    """A successful commit removes only the media made obsolete by the change."""
    with transaction.atomic():
        operation(media_record.attachment)
        assert media_record.original.exists()
        assert media_record.thumbnail.exists()

    assert not media_record.original.exists()
    assert not media_record.thumbnail.exists()


def test_replacement_preserves_new_file(media_record):
    """The cleanup callback captures the previous file rather than the mutable field."""
    with transaction.atomic():
        _replace(media_record.attachment)
        replacement = Path(media_record.attachment.file.path)
        content = replacement.read_bytes()
        media_record.attachment.file.name = 'subsequently-mutated-name.png'

    stored = Attachment.objects.get(pk=media_record.pk)
    assert Path(stored.file.path) == replacement
    assert replacement.read_bytes() == content
    assert not media_record.original.exists()


@pytest.mark.parametrize('operation', [_delete, _replace], ids=['delete', 'replace'])
def test_shared_reference_preserves_media(media_record, operation):
    """Another committed attachment keeps a shared original and thumbnail alive."""
    other = Attachment.objects.create(
        library=media_record.attachment.library, file=media_record.name, rank=1,
    )

    operation(media_record.attachment)

    assert Attachment.objects.get(pk=other.pk).file.name == media_record.name
    assert media_record.original.read_bytes() == media_record.content
    assert media_record.thumbnail.exists()


@pytest.mark.parametrize('operation', [_delete, _replace], ids=['delete', 'replace'])
def test_savepoint_rollback_preserves_media(media_record, operation):
    """Committing the outer transaction does not run a reverted savepoint's cleanup."""
    with transaction.atomic():
        with transaction.atomic():
            operation(media_record.attachment)
            transaction.set_rollback(True)

    assert Attachment.objects.get(pk=media_record.pk).file.name == media_record.name
    assert media_record.original.read_bytes() == media_record.content
    assert media_record.thumbnail.exists()


def test_failed_autocommit_save_preserves_previous_media(media_record):
    """A failed SQL update cannot delete the file captured by pre_save."""
    media_record.attachment.file = _image('invalid-update.png')
    media_record.attachment.title = None

    with pytest.raises(IntegrityError):
        media_record.attachment.save(update_fields=['file', 'title'])

    assert Attachment.objects.get(pk=media_record.pk).file.name == media_record.name
    assert media_record.original.read_bytes() == media_record.content
    assert media_record.thumbnail.exists()


def test_partial_update_preserves_persisted_file(media_record):
    """An in-memory replacement excluded from update_fields does not trigger cleanup."""
    media_record.attachment.file = _image('unsaved-replacement.png')
    media_record.attachment.title = 'Changed title'

    media_record.attachment.save(update_fields=['title'])

    assert Attachment.objects.get(pk=media_record.pk).file.name == media_record.name
    assert media_record.original.read_bytes() == media_record.content
    assert media_record.thumbnail.exists()


def test_raw_save_preserves_previous_media(media_record):
    """Loading a raw file reference does not perform normal replacement cleanup."""
    media_record.attachment.file.name = 'fixture-reference.png'

    media_record.attachment.save_base(raw=True, update_fields=['file'])

    assert Attachment.objects.get(pk=media_record.pk).file.name == 'fixture-reference.png'
    assert media_record.original.read_bytes() == media_record.content
    assert media_record.thumbnail.exists()


def test_storage_failure_keeps_database_commit(media_record, monkeypatch, caplog):
    """A failed storage deletion preserves the database's confirmed result."""
    def fail_delete(name):
        raise OSError('private-storage-value ' + name)

    monkeypatch.setattr(media_record.attachment.file.storage, 'delete', fail_delete)

    with caplog.at_level(logging.ERROR, logger='django.db.models'):
        media_record.attachment.delete()

    assert not Attachment.objects.filter(pk=media_record.pk).exists()
    assert media_record.original.read_bytes() == media_record.content
    assert caplog.messages == ['Attachment cleanup failed: operation=delete error_type=OSError']
    assert caplog.records[0].exc_info is None


def test_storage_failure_allows_following_callback(media_record, monkeypatch):
    """A failed cleanup does not prevent subsequent callbacks on the commit."""
    def fail_delete(name):
        raise OSError('Synthetic storage failure')

    monkeypatch.setattr(media_record.attachment.file.storage, 'delete', fail_delete)
    completed = []

    with transaction.atomic():
        media_record.attachment.delete()
        transaction.on_commit(lambda: completed.append('committed'))

    assert completed == ['committed']
    assert not Attachment.objects.filter(pk=media_record.pk).exists()


@pytest.fixture
def isolated_alias(django_db_blocker):
    """Create a separate in-memory connection without changing project settings."""
    alias = 'attachment_cleanup_test'
    config = deepcopy(connections['default'].settings_dict)
    config['NAME'] = ':memory:'
    connections.databases[alias] = config
    with django_db_blocker.unblock():
        connection = connections[alias]
        with connection.schema_editor() as editor:
            editor.create_model(Library)
            editor.create_model(Attachment)
        try:
            yield alias
        finally:
            connection.close()
            del connections[alias]
            del connections.databases[alias]


def test_replacement_waits_for_own_connection_commit(isolated_alias):
    """A replacement on another alias waits for that alias's transaction."""
    library = Library.objects.using(isolated_alias).create(title='Other connection')
    attachment = Attachment.objects.using(isolated_alias).create(library=library, file=_image(), rank=0)
    original = Path(attachment.file.path)

    with transaction.atomic(using=isolated_alias):
        attachment.file = _image('other-connection-replacement.png')
        attachment.save(using=isolated_alias, update_fields=['file'])
        assert original.exists()

    assert not original.exists()
    assert Path(Attachment.objects.using(isolated_alias).get(pk=attachment.pk).file.path).exists()


def test_shared_reference_guard_uses_own_connection(isolated_alias):
    """References on the operation's alias preserve its shared file after commit."""
    library = Library.objects.using(isolated_alias).create(title='Shared on other connection')
    attachment = Attachment.objects.using(isolated_alias).create(library=library, file=_image(), rank=0)
    original = Path(attachment.file.path)
    shared_name = attachment.file.name
    shared = Attachment.objects.using(isolated_alias).create(library=library, file=shared_name, rank=1)
    thumbnail = get_thumbnailer(attachment.file).get_thumbnail({'size': (2, 2)})

    attachment.file = _image('other-reference-replacement.png')
    attachment.save(using=isolated_alias, update_fields=['file'])

    assert original.exists()
    assert Path(thumbnail.path).exists()
    assert Attachment.objects.using(isolated_alias).get(pk=shared.pk).file.name == shared_name


def _drop_attachment_table(alias):
    """Make the reference query fail in an isolated in-memory test database."""
    with connections[alias].schema_editor() as editor:
        editor.delete_model(Attachment)


def test_reference_query_failure_preserves_file(isolated_alias, caplog):
    """A failed post-commit reference lookup preserves the file for diagnosis."""
    library = Library.objects.using(isolated_alias).create(title='Unavailable reference table')
    attachment = Attachment.objects.using(isolated_alias).create(library=library, file=_image(), rank=0)
    original = Path(attachment.file.path)
    content = original.read_bytes()
    completed = []

    with caplog.at_level(logging.ERROR, logger='django.db.models'), transaction.atomic(using=isolated_alias):
        transaction.on_commit(lambda: _drop_attachment_table(isolated_alias), using=isolated_alias)
        attachment.file = _image('reference-query-replacement.png')
        attachment.save(using=isolated_alias, update_fields=['file'])
        transaction.on_commit(lambda: completed.append('committed'), using=isolated_alias)

    assert original.read_bytes() == content
    assert Library.objects.using(isolated_alias).filter(pk=library.pk).exists()
    assert completed == ['committed']
    assert caplog.messages == ['Attachment cleanup failed: operation=replace error_type=OperationalError']
    assert caplog.records[0].exc_info is None
