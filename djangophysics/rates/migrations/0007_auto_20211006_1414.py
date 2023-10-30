# Generated by Django 3.2.5 on 2021-10-06 14:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rates', '0006_alter_rate_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='RateServiceFetch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fetch_date', models.DateTimeField(auto_created=True, verbose_name='Date of fetching')),
                ('service', models.CharField(max_length=255, verbose_name='name of the rate fetch ing service')),
                ('value_date', models.DateField(verbose_name='Date of the value that has been fetched')),
            ],
        ),
        migrations.AlterField(
            model_name='rate',
            name='value_date',
            field=models.DateField(db_index=True, verbose_name='Date of value'),
        ),
        migrations.AddIndex(
            model_name='rate',
            index=models.Index(fields=['user', 'key'], name='rates_rate_user_id_0baa71_idx'),
        ),
    ]