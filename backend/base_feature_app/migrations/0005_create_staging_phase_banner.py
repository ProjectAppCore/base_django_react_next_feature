from django.db import migrations, models


def seed_singleton(apps, schema_editor):
    StagingPhaseBanner = apps.get_model('base_feature_app', 'StagingPhaseBanner')
    StagingPhaseBanner.objects.get_or_create(pk=1)


def unseed_singleton(apps, schema_editor):
    StagingPhaseBanner = apps.get_model('base_feature_app', 'StagingPhaseBanner')
    StagingPhaseBanner.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base_feature_app', '0004_passwordcode'),
    ]

    operations = [
        migrations.CreateModel(
            name='StagingPhaseBanner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_visible', models.BooleanField(default=True)),
                ('current_phase', models.CharField(
                    choices=[('design', 'Etapa de diseño'), ('development', 'Etapa de desarrollo')],
                    default='design',
                    max_length=20,
                )),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('design_duration_days', models.PositiveIntegerField(default=5)),
                ('development_duration_days', models.PositiveIntegerField(default=10)),
                ('contact_whatsapp', models.CharField(default='+57 323 8122373', max_length=20)),
                ('contact_email', models.EmailField(default='contact@example.com', max_length=254)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Staging Phase Banner',
                'verbose_name_plural': 'Staging Phase Banner',
            },
        ),
        migrations.RunPython(seed_singleton, unseed_singleton),
    ]
