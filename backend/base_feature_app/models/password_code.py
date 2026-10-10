from datetime import timedelta

from django.contrib.auth.tokens import default_token_generator
from django.db import models, transaction
from django.utils import timezone

from base_feature_app.models import User


class PasswordCode(models.Model):
    """Store single-use password-reset tokens with a fifteen-minute lifetime."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_codes')
    code = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"Code for {self.user.email} - {self.code}"

    @classmethod
    def generate_code(cls, user):
        """Replace pending challenges while holding the account's database lock."""
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            cls.objects.filter(user=locked_user, used=False).update(used=True)
            return cls.objects.create(
                user=locked_user,
                code=default_token_generator.make_token(locked_user),
            )

    def is_valid(self):
        """Require an unused, recent token matching the current account state."""
        if self.used or timezone.now() - self.created_at >= timedelta(minutes=15):
            return False
        return default_token_generator.check_token(self.user, self.code)
