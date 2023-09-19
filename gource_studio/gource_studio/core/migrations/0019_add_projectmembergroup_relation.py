# Generated by Django 3.2.15 on 2023-09-19 05:23

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('core', '0018_add_projectbuild_audio_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projectmember',
            name='role',
            field=models.CharField(choices=[('viewer', 'Viewer'), ('developer', 'Developer'), ('maintainer', 'Maintainer')], default='viewer', max_length=32),
        ),
        migrations.CreateModel(
            name='ProjectMemberGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('viewer', 'Viewer'), ('developer', 'Developer'), ('maintainer', 'Maintainer')], default='viewer', max_length=32)),
                ('date_added', models.DateTimeField(auto_now=True)),
                ('added_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='projects', to='auth.group')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='member_groups', to='core.project')),
            ],
            options={
                'ordering': ('-date_added',),
                'unique_together': {('project', 'group')},
            },
        ),
    ]
