# -*- coding: utf-8 -*-
from io import BytesIO
import os
from tempfile import TemporaryDirectory

from easy_thumbnails.files import get_thumbnailer
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import Library, Attachment


class AttachmentModelTest(TestCase):
	def setUp(self):
		media_root = self.enterContext(TemporaryDirectory())
		self.enterContext(override_settings(MEDIA_ROOT=media_root))

	def create_library(self, title='Test'):
		library = Library(title=title)
		library.save()
		return library

	def create_attachment(self, filename, data, library=None, **kwargs):
		if library == None:
			library = self.create_library()
		uploaded_file = SimpleUploadedFile(filename, data)
		attachment = Attachment(file=uploaded_file, library=library, **kwargs)
		attachment.save()
		return attachment

	def create_image(self, image_size):
		im = Image.new('RGB', image_size)
		data = BytesIO()
		im.save(data, 'JPEG')
		return data.getvalue()

	def test_library(self):
		title = 'Test'
		library = self.create_library()
		self.assertEqual(library.title, title)
		self.assertIsNone(library.primary_attachment)
		library.delete()

	def test_upload_file(self):
		data = b'data'
		attachment = self.create_attachment('upload.txt', data)
		self.assertEqual(attachment.original_name, 'upload.txt')
		self.assertEqual(attachment.rank, 0)
		self.assertEqual(attachment.filesize, len(data))
		self.assertIsNone(attachment.image_width)
		attachment.delete()

	def test_upload_image(self):
		image_size = (5, 10)
		attachment = self.create_attachment('image.jpg', self.create_image(image_size))
		self.assertEqual(attachment.image_width, image_size[0])
		self.assertEqual(attachment.image_height, image_size[1])
		attachment.delete()

	def test_rank_create_delete(self):
		library = self.create_library()
		attachments = [
			self.create_attachment('upload.txt', b'', library),
			self.create_attachment('upload.txt', b'', library),
		]
		self.assertEqual(attachments[0].rank, 0)
		self.assertEqual(attachments[1].rank, 1)

		# ranks from other library
		library2 = self.create_library()
		attachments2 = [
			self.create_attachment('upload.txt', b'', library2),
			self.create_attachment('upload.txt', b'', library2),
		]
		self.assertEqual(attachments2[0].rank, 0)
		self.assertEqual(attachments2[1].rank, 1)

		# change rank when delete
		attachments[0].delete()
		attachments[1].refresh_from_db()
		self.assertEqual(attachments[1].rank, 0)
		attachments.pop(0)
		# preserve rank when delete last
		attachments2[1].delete()
		attachments2[0].refresh_from_db()
		self.assertEqual(attachments2[0].rank, 0)
		attachments2.pop(1)

		# insert at specific position
		attachment = self.create_attachment('upload.txt', b'', library, rank=0)
		attachments[0].refresh_from_db()
		attachments.insert(0, attachment)
		self.assertEqual(attachments[0].rank, 0)
		self.assertEqual(attachments[1].rank, 1)

		attachments[0].delete()
		attachments[1].delete()
		attachments2[0].delete()

	def test_rank_move(self):
		library = self.create_library()
		count = 5
		attachments = []
		result_order = list(range(5))
		for i in range(count):
			attachments.append(self.create_attachment('upload.txt', b'', library))

		for i in range(count):
			attachments[i].refresh_from_db()
			self.assertEqual(attachments[i].rank, result_order[i])

		attachments[2].move_to(2) # position not changed

		for i in range(count):
			attachments[i].refresh_from_db()
			self.assertEqual(attachments[i].rank, result_order[i])

		attachments[3].move_to(1)
		result_order = [0, 2, 3, 1, 4]

		for i in range(count):
			attachments[i].refresh_from_db()
			self.assertEqual(attachments[i].rank, result_order[i])
			# reset
			attachments[i].rank = i
			attachments[i].save()

		attachments[1].move_to(3)
		result_order = [0, 3, 1, 2, 4]

		for i in range(count):
			attachments[i].refresh_from_db()
			self.assertEqual(attachments[i].rank, result_order[i])
			# reset
			attachments[i].rank = i
			attachments[i].save()

		for i in range(count):
			attachments[i].delete()

	def test_delete(self):
		attachment = self.create_attachment('upload.png', self.create_image((5, 5)))
		thumbnailer = get_thumbnailer(attachment.file)
		thumbnail = thumbnailer.get_thumbnail({'crop': True, 'size': (1, 1)})

		self.assertTrue(os.path.exists(attachment.file.path))
		self.assertTrue(os.path.exists(thumbnail.path))

		file_path = attachment.file.path
		with self.captureOnCommitCallbacks(execute=True):
			attachment.delete()
		self.assertFalse(os.path.exists(file_path))
		self.assertFalse(os.path.exists(thumbnail.path))

	def test_update_library(self):
		library = self.create_library()
		attachment = self.create_attachment('upload.txt', '', library=library)
		library.refresh_from_db()
		self.assertIsNone(library.primary_attachment)
		Library.objects.filter(pk=library.pk).update_primary_image()
		library.refresh_from_db()
		self.assertEqual(library.primary_attachment, attachment)
