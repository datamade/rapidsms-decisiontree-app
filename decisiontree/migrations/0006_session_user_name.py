# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-09-14 12:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('decisiontree', '0005_auto_20180808_1125'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='user_name',
            field=models.CharField(blank=True, max_length=160),
        ),
    ]
