import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_detallepedido_precio'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='direccion',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='producto',
            name='precio',
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AlterField(
            model_name='producto',
            name='stock',
            field=models.PositiveIntegerField(),
        ),
        migrations.AlterField(
            model_name='detallepedido',
            name='cantidad',
            field=models.PositiveIntegerField(
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
    ]