# Generated by Django 4.0.5 on 2022-06-29 01:26

import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0007_order_profile_and_message"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="message",
            options={"ordering": ["-updated_at"]},
        ),
        migrations.AlterModelOptions(
            name="profile",
            options={"ordering": ["staleness"]},
        ),
        migrations.AddField(
            model_name="profile",
            name="staleness",
            field=models.DurationField(default=datetime.timedelta(0)),
        ),
    ]
