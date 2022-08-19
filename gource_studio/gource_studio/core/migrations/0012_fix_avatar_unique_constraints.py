# Generated by Django 3.1.4 on 2022-08-19 04:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_add_project_url_active'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='projectuseravatar',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='projectuseravataralias',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='useravatar',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelOptions(
            name='useravataralias',
            options={'ordering': ('name',)},
        ),
        migrations.AlterField(
            model_name='project',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='projectbuild',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='projectbuildoption',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='projectcaption',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='projectmember',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='projectoption',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='projectuseravatar',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='projectuseravatar',
            name='name',
            field=models.CharField(max_length=256),
        ),
        migrations.AlterField(
            model_name='projectuseravataralias',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='projectuseravataralias',
            name='name',
            field=models.CharField(max_length=256),
        ),
        migrations.AlterField(
            model_name='useravatar',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='useravataralias',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterUniqueTogether(
            name='projectuseravatar',
            unique_together={('project', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='projectuseravataralias',
            unique_together={('avatar', 'name')},
        ),
    ]
