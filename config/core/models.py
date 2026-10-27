from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=255, blank=True)
    documento_identidad = models.CharField(max_length=30, unique=True, null=True, blank=True)

    def __str__(self):
        return f"{self.nombre} - {self.documento_identidad or self.telefono}"


class Proveedor(models.Model):
    nombre = models.CharField(max_length=120)
    documento_fiscal = models.CharField(max_length=30, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    correo = models.EmailField(blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField()

    def __str__(self):
        return self.nombre


class Pedido(models.Model):
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_CANCELADO = 'cancelado'
    ESTADOS = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_CANCELADO, 'Cancelado'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_PENDIENTE)
    def total(self):
        return sum(d.subtotal() for d in self.detallepedido_set.all())

    def __str__(self):
        return f"Pedido {self.id} - {self.cliente.nombre}"
    
class DetallePedido(models.Model):
    pedido = models.ForeignKey('Pedido', on_delete=models.CASCADE)
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    default=0
)

    def subtotal(self):
        return self.cantidad * self.precio

    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad}"


class RecepcionMercancia(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='recepciones')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='recepciones')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    fecha = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f"Recepción #{self.id} - {self.proveedor.nombre} - {self.producto.nombre}"


class Perfil(models.Model):

    ROL_ADMIN = 'admin'
    ROL_CLIENTE = 'cliente'
    ROL_PROVEEDOR = 'proveedor'

    ROLES = [
        (ROL_ADMIN, 'Administrador'),
        (ROL_CLIENTE, 'Cliente'),
        (ROL_PROVEEDOR, 'Proveedor'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil'
    )

    tipo_usuario = models.CharField(
        max_length=10,
        choices=ROLES,
        default=ROL_CLIENTE
    )

    cliente = models.OneToOneField(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuenta',
    )
    proveedor = models.OneToOneField(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuenta',
    )

    def __str__(self):
        return f"{self.user.username} - {self.tipo_usuario}"