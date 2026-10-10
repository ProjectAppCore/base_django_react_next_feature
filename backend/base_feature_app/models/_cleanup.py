from django_attachments.models import Library


def _delete_orphan_library(library_id: int | None, *, using: str) -> None:
    """Delete a library only after its last blog or product has been removed."""
    library = Library.objects.using(using).filter(
        pk=library_id,
        blog_image__isnull=True,
        products_with_attachment__isnull=True,
    ).first()
    if library is not None:
        library.delete(using=using)
