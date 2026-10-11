from typing import ClassVar

from django.db import migrations, models


def invalidate_legacy_codes(apps, schema_editor):
    """Require a fresh recovery token after retiring short reset codes."""
    password_code = apps.get_model('base_feature_app', 'PasswordCode')
    password_code.objects.using(schema_editor.connection.alias).filter(
        used=False,
    ).update(used=True)


class Migration(migrations.Migration):
    dependencies: ClassVar = [
        ('base_feature_app', '0005_create_staging_phase_banner'),
    ]

    operations: ClassVar = [
        migrations.AlterField(
            model_name='passwordcode',
            name='code',
            field=models.CharField(max_length=64),
        ),
        # Deliberately irreversible: rollback must never reactivate old codes
        # or shrink the column while recovery tokens remain in the table.
        migrations.RunPython(invalidate_legacy_codes),
    ]
