# -*- coding: utf-8 -*-
import mimetypes
from io import BytesIO
from os import path
from uuid import uuid4

from PIL import Image
from django.db import models
from django.db.models import F, Max, Subquery, OuterRef
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_cleanup import cleanup
from easy_thumbnails.fields import ThumbnailerField

from .utils import parse_mimetype


class TimestampModelMixin(models.Model):
	created = models.DateTimeField(_("Created"), editable=False, db_index=True)
	updated = models.DateTimeField(_("Updated"), editable=False, db_index=True)

	def save(self, *args, **kwargs):
		self.updated = timezone.now()
		if not self.id and not self.created:
			self.created = self.updated
		return super().save(*args, **kwargs)

	class Meta:
		abstract = True


def upload_path_handler(instance, filename):
	pk = instance.library.pk
	filename = str(uuid4()) + path.splitext(filename)[1]
	return path.join('attachments', "{0:02x}".format(pk % 256), str(pk), filename)


class LibraryQuerySet(models.QuerySet):
	def update_primary_image(self):
		# Subquery to get the primary attachment for each library by lowest rank
		primary_attachment = Subquery(Attachment.objects
			.filter(library=OuterRef('pk'))
			.order_by('rank')
			.values('pk')[:1])
		return self.update(primary_attachment=primary_attachment)


class Library(TimestampModelMixin, models.Model):
	objects = LibraryQuerySet.as_manager()

	title = models.CharField(
		verbose_name=_("Name"),
		max_length=255,
		blank=True
	)
	primary_attachment = models.ForeignKey(
		'Attachment',
		verbose_name=_("Primary attachment"),
		blank=True,
		null=True,
		on_delete=models.SET_NULL,
		related_name='attachments_library'
	)

	class Meta:
		verbose_name = _("Library")
		verbose_name_plural = _("Libraries")

	def __str__(self):
		if self.title:
			return self.title
		elif self.pk:
			return 'Library #%d' % self.pk
		else:
			return 'Library'


class AttachmentQuerySet(models.QuerySet):
	def images(self):
		return self.filter(image_width__isnull=False)


@cleanup.ignore
class Attachment(TimestampModelMixin, models.Model):
	objects = AttachmentQuerySet.as_manager()

	library = models.ForeignKey(
		Library,
		verbose_name=_("Library"),
		on_delete=models.CASCADE
	)
	rank = models.IntegerField(
		verbose_name=_("Rank")
	)
	original_name = models.CharField(
		max_length=255,
		verbose_name=_("Original name")
	)
	file = ThumbnailerField(
		verbose_name=_("File"),
		upload_to=upload_path_handler
	)
	filesize = models.BigIntegerField(
		verbose_name=_("File size"),
	)
	mimetype = models.CharField(
		verbose_name=_("File type"),
		max_length=200,
		blank=True
	)
	image_width = models.IntegerField(
		verbose_name=_("Image width"),
		blank=True,
		null=True
	)
	image_height = models.IntegerField(
		verbose_name=_("Image height"),
		blank=True,
		null=True
	)
	title = models.CharField(
		verbose_name=_("Name"),
		max_length=255,
		blank=True
	)
	caption = models.TextField(
		verbose_name=_("Caption"),
		blank=True
	)
	options = models.TextField(
		verbose_name=_("Options"),
		blank=True
	)

	class Meta:
		verbose_name = _("Attachment")
		verbose_name_plural = _("Attachments")
		ordering = ('-library', 'rank')
		indexes = [
			models.Index(fields=['library', 'rank'])
		]

	def __str__(self):
		return self.original_name

	@property
	def is_image(self):
		return self.image_width is not None

	@property
	def mimetype_info(self):
		return parse_mimetype(self.original_name)

	def save(self, *args, **kwargs):
		if not self.original_name:
			self.original_name = self.file.name
		if self.original_name:
			self.original_name = self.original_name[:255]
			self.mimetype = (mimetypes.guess_type(self.original_name)[0] or '')[:200]
		if self.rank is None:
			next_rank = self._rank_queryset().aggregate(max_rank=Max('rank'))['max_rank']
			if next_rank is None:
				next_rank = 0
			else:
				next_rank += 1
			self.rank = next_rank
		else:
			if self.pk is None:
				self._rank_queryset().filter(rank__gte=self.rank).update(rank=F('rank')+1)
		if self.file:
			self.filesize = self.file.size
			source = BytesIO(self.file.read())
			try:
				image = Image.open(source)
				self.image_width, self.image_height = image.size
			except IOError:
				pass
			finally:
				self.file.seek(0)
		else:
			self.filesize = -1
			self.image_width = None
			self.image_height = None
		return super().save(*args, **kwargs)

	def delete(self, *args, **kwargs):
		self._rank_queryset().filter(rank__gt=self.rank).update(rank=F('rank')-1)
		return super().delete(*args, **kwargs)

	def move_to(self, position):
		if position == self.rank:
			return
		if self.rank > position:
			self._rank_queryset().filter(rank__lt=self.rank, rank__gte=position).update(rank=F('rank')+1)
		else:
			self._rank_queryset().filter(rank__gt=self.rank, rank__lte=position).update(rank=F('rank')-1)
		self.rank = position
		self.save()

	def _rank_queryset(self):
		return Attachment.objects.filter(library=self.library).order_by('rank')
