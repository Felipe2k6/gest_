from django.contrib import admin
from .models import Cliente, Producto, Pedido, DetallePedido, Perfil, Proveedor, RecepcionMercancia


admin.site.register(Pedido)
admin.site.register(DetallePedido)
admin.site.register(Cliente)
admin.site.register(Producto)
admin.site.register(Perfil)
admin.site.register(Proveedor)
admin.site.register(RecepcionMercancia)