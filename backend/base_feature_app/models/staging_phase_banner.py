from datetime import timedelta
from functools import cached_property
from math import ceil

from django.db import models
from django.utils import timezone


class StagingPhaseBanner(models.Model):
    """Singleton model controlling the staging review banner shown to clients.

    Only one row exists (pk=1). Hide via `is_visible=False` instead of deleting.
    """

    PHASE_DESIGN = 'design'
    PHASE_DEVELOPMENT = 'development'
    PHASE_CHOICES = [
        (PHASE_DESIGN, 'Etapa de diseño'),
        (PHASE_DEVELOPMENT, 'Etapa de desarrollo'),
    ]
    PHASE_LABELS_I18N = {
        PHASE_DESIGN: {'es': 'Etapa de diseño', 'en': 'Design phase'},
        PHASE_DEVELOPMENT: {'es': 'Etapa de desarrollo', 'en': 'Development phase'},
    }

    is_visible = models.BooleanField(default=True)
    current_phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default=PHASE_DESIGN)
    started_at = models.DateTimeField(null=True, blank=True)
    design_duration_days = models.PositiveIntegerField(default=5)
    development_duration_days = models.PositiveIntegerField(default=10)
    contact_whatsapp = models.CharField(max_length=20, default='+57 323 8122373')
    contact_email = models.EmailField(default='contact@example.com')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Staging Phase Banner'
        verbose_name_plural = 'Staging Phase Banner'

    def __str__(self):
        return f'StagingPhaseBanner(phase={self.current_phase}, visible={self.is_visible})'

    @property
    def phase_duration_days(self):
        if self.current_phase == self.PHASE_DESIGN:
            return self.design_duration_days
        return self.development_duration_days

    @cached_property
    def expires_at(self):
        if not self.started_at:
            return None
        return self.started_at + timedelta(days=self.phase_duration_days)

    @property
    def days_remaining(self):
        if self.expires_at is None:
            return None
        delta = self.expires_at - timezone.now()
        if delta.total_seconds() <= 0:
            return 0
        return ceil(delta.total_seconds() / 86400)

    @property
    def is_expired(self):
        return self.expires_at is not None and timezone.now() >= self.expires_at

    @property
    def phase_labels(self):
        return self.PHASE_LABELS_I18N.get(self.current_phase, {'es': '', 'en': ''})

    def save(self, *args, **kwargs):
        self.pk = 1
        # cached_property persists on the instance; invalidate on save so
        # admins editing started_at see fresh values on the next access.
        self.__dict__.pop('expires_at', None)
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        try:
            return cls.objects.get(pk=1)
        except cls.DoesNotExist:
            instance, _ = cls.objects.get_or_create(pk=1)
            return instance
