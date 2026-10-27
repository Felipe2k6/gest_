from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from .models import Cliente, Producto, Pedido, DetallePedido, Perfil, Proveedor, RecepcionMercancia
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .utils import es_admin, es_cliente, es_proveedor, perfil_usuario
from django.db.models import Sum, F
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal, InvalidOperation


def _inicio_por_rol(user):
    if es_admin(user):
        return '/dashboard/'
    if es_proveedor(user):
        return '/productos/'
    return '/pedidos/'


def _puede_gestionar_productos(user):
    return es_admin(user) or es_proveedor(user)


def _validar_datos_cuenta(datos):
    if datos.get('crear_cuenta') != 'on':
        return None, None, None

    username = datos.get('username', '').strip()
    password = datos.get('password', '')
    password_confirmation = datos.get('password_confirmation', '')

    if not username:
        return None, None, 'El nombre de usuario es obligatorio para crear la cuenta'
    if len(username) > 150:
        return None, None, 'El nombre de usuario no puede superar 150 caracteres'
    if User.objects.filter(username__iexact=username).exists():
        return None, None, 'Ese nombre de usuario ya está registrado'
    if not password:
        return None, None, 'La contraseña es obligatoria para crear la cuenta'
    if password != password_confirmation:
        return None, None, 'Las contraseñas no coinciden'

    return username, password, None


def _crear_cuenta_vinculada(username, password, role, *, cliente=None, proveedor=None, email='',
                            first_name=''):
    usuario = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
    )
    perfil = usuario.perfil
    perfil.tipo_usuario = role
    perfil.cliente = cliente
    perfil.proveedor = proveedor
    perfil.save(update_fields=['tipo_usuario', 'cliente', 'proveedor'])


def _guardar_cliente(cliente, datos):
    cliente.nombre = datos.get('nombre', '').strip()
    cliente.telefono = datos.get('telefono', '').strip()
    cliente.direccion = datos.get('direccion', '').strip()
    cliente.documento_identidad = datos.get('documento_identidad', '').strip() or None

    if not cliente.documento_identidad:
        return 'El documento de identidad es obligatorio'
    if not cliente.direccion:
        return 'La dirección del cliente es obligatoria'

    try:
        cliente.full_clean()
        cliente.save()
    except ValidationError as error:
        if 'documento_identidad' in error.message_dict:
            return 'Ya existe un cliente con ese documento de identidad'
        if 'telefono' in error.message_dict:
            return 'Ya existe un cliente con ese teléfono'
        return 'Completa correctamente todos los datos del cliente'
    except IntegrityError:
        return 'Ya existe un cliente con ese teléfono o documento de identidad'

    return None


def _guardar_producto(producto, datos):
    producto.nombre = datos.get('nombre', '').strip()

    try:
        producto.precio = Decimal(datos.get('precio', ''))
        producto.stock = int(datos.get('stock', ''))
    except (InvalidOperation, TypeError, ValueError):
        return 'Ingresa un precio y una cantidad de stock válidos'

    if not producto.precio.is_finite() or producto.precio < 0 or producto.stock < 0:
        return 'El precio y el stock no pueden ser negativos'

    try:
        producto.full_clean()
        producto.save()
    except ValidationError as error:
        if 'nombre' in error.message_dict:
            return 'Ya existe un producto con ese nombre'
        return 'Completa correctamente todos los datos del producto'
    except IntegrityError:
        return 'Ya existe un producto con ese nombre'

    return None

@login_required
def lista_clientes(request):
    if not es_admin(request.user):
        return redirect('/pedidos/')

    clientes = Cliente.objects.all()
    return render(request, 'clientes.html', {'clientes': clientes})

@login_required
def crear_cliente(request):
    if not es_admin(request.user):
        return redirect('/pedidos/')

    if request.method == 'POST':
        cliente = Cliente()
        form_data = request.POST
        username, password, error = _validar_datos_cuenta(form_data)
        if error:
            return render(request, 'crear_cliente.html', {
                'error': error,
                'cliente': cliente,
                'form_data': form_data,
            })

        try:
            with transaction.atomic():
                with transaction.atomic():
                    error = _guardar_cliente(cliente, form_data)
                if error:
                    return render(request, 'crear_cliente.html', {
                        'error': error,
                        'cliente': cliente,
                        'form_data': form_data,
                    })
                if username:
                    _crear_cuenta_vinculada(
                        username,
                        password,
                        Perfil.ROL_CLIENTE,
                        cliente=cliente,
                        email=form_data.get('email', '').strip(),
                        first_name=cliente.nombre,
                    )
        except IntegrityError:
            return render(request, 'crear_cliente.html', {
                'error': 'No se pudo crear el cliente y su cuenta. Verifica los datos e inténtalo de nuevo.',
                'cliente': cliente,
                'form_data': form_data,
            })

        messages.success(
            request,
            'El cliente y su cuenta se crearon correctamente' if username
            else 'El cliente se registró correctamente',
        )
        return redirect('/clientes/')

    return render(request, 'crear_cliente.html', {'cliente': Cliente(), 'form_data': {}})

@login_required
def editar_cliente(request, id):
    if not es_admin(request.user):
        return redirect('/pedidos/')

    cliente = get_object_or_404(Cliente, id=id)

    if request.method == 'POST':
        error = _guardar_cliente(cliente, request.POST)
        if not error:
            return redirect('/clientes/')
        return render(request, 'editar_cliente.html', {'cliente': cliente, 'error': error})

    return render(request, 'editar_cliente.html', {'cliente': cliente})

@login_required
def eliminar_cliente(request, id):
    if not es_admin(request.user):
        return redirect('/pedidos/')

    cliente = get_object_or_404(Cliente, id=id)
    cliente.delete()
    return redirect('/clientes/')


def _contexto_usuario(form_data=None):
    return {
        'form_data': form_data or {},
    }


@login_required
def lista_usuarios(request):
    if not es_admin(request.user):
        return redirect(_inicio_por_rol(request.user))

    usuarios = User.objects.select_related('perfil', 'perfil__cliente', 'perfil__proveedor').order_by('username')
    return render(request, 'usuarios.html', {'usuarios': usuarios})


@login_required
def crear_usuario(request):
    if not es_admin(request.user):
        return redirect(_inicio_por_rol(request.user))

    if request.method != 'POST':
        return render(request, 'crear_usuario.html', _contexto_usuario())

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    password_confirmation = request.POST.get('password_confirmation', '')
    role = Perfil.ROL_ADMIN
    cliente = None
    proveedor = None
    error = None

    if not username:
        error = 'El nombre de usuario es obligatorio'
    elif User.objects.filter(username__iexact=username).exists():
        error = 'Ese nombre de usuario ya está registrado'
    elif role not in dict(Perfil.ROLES):
        error = 'Selecciona un rol válido'
    elif password != password_confirmation:
        error = 'Las contraseñas no coinciden'
    elif not password:
        error = 'La contraseña es obligatoria'
    if error:
        context = _contexto_usuario(request.POST)
        context['error'] = error
        return render(request, 'crear_usuario.html', context)

    try:
        with transaction.atomic():
            nuevo_usuario = User.objects.create_user(
                username=username,
                password=password,
                email=request.POST.get('email', '').strip(),
                first_name=request.POST.get('first_name', '').strip(),
                last_name=request.POST.get('last_name', '').strip(),
            )
            perfil = nuevo_usuario.perfil
            perfil.tipo_usuario = role
            perfil.cliente = cliente
            perfil.proveedor = proveedor
            perfil.save(update_fields=['tipo_usuario', 'cliente', 'proveedor'])
    except IntegrityError:
        context = _contexto_usuario(request.POST)
        context['error'] = 'No se pudo crear la cuenta. Verifica que el usuario y el vínculo estén disponibles.'
        return render(request, 'crear_usuario.html', context)

    messages.success(request, f'La cuenta {username} se creó correctamente')
    return redirect('/usuarios/')


def _guardar_proveedor(proveedor, datos):
    proveedor.nombre = datos.get('nombre', '').strip()
    proveedor.documento_fiscal = datos.get('documento_fiscal', '').strip() or None
    proveedor.telefono = datos.get('telefono', '').strip()
    proveedor.correo = datos.get('correo', '').strip()
    proveedor.direccion = datos.get('direccion', '').strip()

    try:
        proveedor.full_clean()
        proveedor.save()
    except ValidationError as error:
        if 'documento_fiscal' in error.message_dict:
            return 'Ya existe un proveedor con ese documento fiscal'
        return 'Completa correctamente los datos del proveedor'
    except IntegrityError:
        return 'Ya existe un proveedor con ese documento fiscal'

    return None


@login_required
def lista_proveedores(request):
    if not es_admin(request.user):
        return redirect(_inicio_por_rol(request.user))

    proveedores = Proveedor.objects.annotate(cuenta_usuario=F('cuenta__user__username')).order_by('nombre')
    return render(request, 'proveedores.html', {'proveedores': proveedores})


@login_required
def crear_proveedor(request):
    if not es_admin(request.user):
        return redirect(_inicio_por_rol(request.user))

    proveedor = Proveedor()
    if request.method == 'POST':
        form_data = request.POST
        username, password, error = _validar_datos_cuenta(form_data)
        if error:
            return render(request, 'crear_proveedor.html', {
                'proveedor': proveedor,
                'error': error,
                'form_data': form_data,
            })

        try:
            with transaction.atomic():
                with transaction.atomic():
                    error = _guardar_proveedor(proveedor, form_data)
                if error:
                    return render(request, 'crear_proveedor.html', {
                        'proveedor': proveedor,
                        'error': error,
                        'form_data': form_data,
                    })
                if username:
                    _crear_cuenta_vinculada(
                        username,
                        password,
                        Perfil.ROL_PROVEEDOR,
                        proveedor=proveedor,
                        email=proveedor.correo,
                        first_name=proveedor.nombre,
                    )
        except IntegrityError:
            return render(request, 'crear_proveedor.html', {
                'proveedor': proveedor,
                'error': 'No se pudo crear el proveedor y su cuenta. Verifica los datos e inténtalo de nuevo.',
                'form_data': form_data,
            })

        messages.success(
            request,
            'El proveedor y su cuenta se crearon correctamente' if username
            else 'El proveedor se registró correctamente',
        )
        return redirect('/proveedores/')

    return render(request, 'crear_proveedor.html', {'proveedor': proveedor})


@login_required
def editar_proveedor(request, id):
    if not es_admin(request.user):
        return redirect(_inicio_por_rol(request.user))

    proveedor = get_object_or_404(Proveedor, pk=id)
    if request.method == 'POST':
        error = _guardar_proveedor(proveedor, request.POST)
        if not error:
            messages.success(request, 'Los datos del proveedor se actualizaron')
            return redirect('/proveedores/')
        return render(request, 'crear_proveedor.html', {
            'proveedor': proveedor,
            'error': error,
            'form_data': request.POST,
        })

    return render(request, 'crear_proveedor.html', {'proveedor': proveedor})


@login_required
def lista_recepciones(request):
    if es_admin(request.user):
        recepciones = RecepcionMercancia.objects.all()
    elif es_proveedor(request.user):
        perfil = perfil_usuario(request.user)
        recepciones = RecepcionMercancia.objects.filter(proveedor_id=perfil.proveedor_id) if perfil.proveedor_id else RecepcionMercancia.objects.none()
    else:
        return redirect(_inicio_por_rol(request.user))

    recepciones = recepciones.select_related('proveedor', 'producto', 'usuario').order_by('-fecha')
    return render(request, 'recepciones.html', {
        'recepciones': recepciones,
        'es_admin': es_admin(request.user),
    })


@login_required
def registrar_recepcion(request):
    if not es_admin(request.user) and not es_proveedor(request.user):
        return redirect(_inicio_por_rol(request.user))

    perfil = perfil_usuario(request.user)
    if es_proveedor(request.user) and not perfil.proveedor_id:
        messages.error(request, 'Tu cuenta no está vinculada a un proveedor')
        return redirect('/productos/')

    productos = Producto.objects.order_by('nombre')
    proveedores = Proveedor.objects.filter(activo=True).order_by('nombre') if es_admin(request.user) else None
    context = {'productos': productos, 'proveedores': proveedores, 'es_admin': es_admin(request.user)}

    if request.method == 'POST':
        try:
            producto_id = int(request.POST.get('producto', ''))
            cantidad = int(request.POST.get('cantidad', ''))
            costo_unitario = Decimal(request.POST.get('costo_unitario', ''))
        except (InvalidOperation, TypeError, ValueError):
            context['error'] = 'Ingresa producto, cantidad y costo válidos'
            context['form_data'] = request.POST
            return render(request, 'registrar_recepcion.html', context)

        proveedor_id = perfil.proveedor_id if es_proveedor(request.user) else request.POST.get('proveedor', '')
        if cantidad < 1 or not costo_unitario.is_finite() or costo_unitario < 0:
            context['error'] = 'La cantidad debe ser positiva y el costo no puede ser negativo'
            context['form_data'] = request.POST
            return render(request, 'registrar_recepcion.html', context)

        try:
            with transaction.atomic():
                producto = Producto.objects.select_for_update().get(pk=producto_id)
                proveedor = Proveedor.objects.get(pk=proveedor_id, activo=True)
                recepcion = RecepcionMercancia(
                    proveedor=proveedor,
                    producto=producto,
                    usuario=request.user,
                    cantidad=cantidad,
                    costo_unitario=costo_unitario,
                    observaciones=request.POST.get('observaciones', '').strip(),
                )
                recepcion.full_clean()
                recepcion.save()
                producto.stock += cantidad
                producto.save(update_fields=['stock'])
        except (Producto.DoesNotExist, Proveedor.DoesNotExist, TypeError, ValueError, ValidationError):
            context['error'] = 'No se pudo registrar la recepción. Revisa el proveedor y el producto.'
            context['form_data'] = request.POST
            return render(request, 'registrar_recepcion.html', context)

        messages.success(request, f'Se registraron {cantidad} unidades de {producto.nombre}')
        return redirect('/recepciones/')

    if es_proveedor(request.user):
        context['proveedor_usuario'] = perfil.proveedor
    return render(request, 'registrar_recepcion.html', context)


@login_required
def lista_productos(request):
    if es_proveedor(request.user):
        perfil = perfil_usuario(request.user)
        productos = Producto.objects.filter(recepciones__proveedor=perfil.proveedor).distinct() if perfil.proveedor_id else Producto.objects.none()
    else:
        productos = Producto.objects.all()
    return render(request, 'productos.html', {
        'productos': productos,
        'puede_gestionar_productos': _puede_gestionar_productos(request.user),
        'es_admin': es_admin(request.user),
    })


@login_required
def crear_producto(request):
    if not es_admin(request.user):
        return redirect(_inicio_por_rol(request.user))

    if request.method == 'POST':
        producto = Producto()
        error = _guardar_producto(producto, request.POST)
        if not error:
            return redirect('/productos/')
        return render(request, 'crear_producto.html', {
            'error': error,
            'producto': producto,
            'form_data': request.POST,
        })

    return render(request, 'crear_producto.html', {'producto': Producto()})


@login_required
def editar_producto(request, id):
    if not _puede_gestionar_productos(request.user):
        return redirect(_inicio_por_rol(request.user))

    producto = get_object_or_404(Producto, id=id)
    perfil = perfil_usuario(request.user)
    if es_proveedor(request.user) and (
        perfil.proveedor_id is None
        or not producto.recepciones.filter(proveedor_id=perfil.proveedor_id).exists()
    ):
        return redirect('/productos/')

    if request.method == 'POST':
        datos = request.POST.copy()
        if es_proveedor(request.user):
            datos['stock'] = str(producto.stock)
        error = _guardar_producto(producto, datos)
        if not error:
            return redirect('/productos/')
        return render(request, 'editar_producto.html', {
            'producto': producto,
            'error': error,
            'form_data': request.POST,
            'es_admin': es_admin(request.user),
        })

    return render(request, 'editar_producto.html', {
        'producto': producto,
        'es_admin': es_admin(request.user),
    })

@login_required
def eliminar_producto(request, id):
    if not es_admin(request.user):
        return redirect(_inicio_por_rol(request.user))

    producto = get_object_or_404(Producto, id=id)
    producto.delete()
    return redirect('/productos/')

@login_required
def lista_pedidos(request):
    if es_admin(request.user):
        pedidos = Pedido.objects.all()
    elif es_cliente(request.user):
        perfil = perfil_usuario(request.user)
        pedidos = Pedido.objects.filter(cliente_id=perfil.cliente_id) if perfil.cliente_id else Pedido.objects.none()
    else:
        return redirect(_inicio_por_rol(request.user))

    return render(request, 'pedidos.html', {'pedidos': pedidos})


@login_required
def crear_pedido(request):
    if not es_admin(request.user) and not es_cliente(request.user):
        return redirect(_inicio_por_rol(request.user))

    perfil = perfil_usuario(request.user)
    clientes = Cliente.objects.all() if es_admin(request.user) else Cliente.objects.filter(pk=perfil.cliente_id)

    if request.method == 'POST':
        if es_admin(request.user):
            cliente_id = request.POST.get('cliente')
            try:
                cliente = Cliente.objects.get(pk=int(cliente_id))
            except (TypeError, ValueError, Cliente.DoesNotExist):
                messages.error(request, 'Selecciona un cliente válido para crear el pedido')
                return render(request, 'crear_pedido.html', {
                    'clientes': clientes,
                    'cliente_seleccionado': cliente_id,
                    'es_admin': True,
                })
        else:
            if not perfil.cliente_id:
                messages.error(request, 'Tu cuenta no está vinculada a un cliente. Contacta al administrador.')
                return redirect('/pedidos/')
            cliente = perfil.cliente

        Pedido.objects.create(
            cliente=cliente,
            usuario=request.user
        )

        return redirect('/pedidos/')

    return render(request, 'crear_pedido.html', {
        'clientes': clientes,
        'es_admin': es_admin(request.user),
        'cliente_perfil': perfil.cliente if es_cliente(request.user) and perfil.cliente_id else None,
    })

@login_required
def agregar_productos(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if not es_admin(request.user) and (
        not es_cliente(request.user)
        or perfil_usuario(request.user).cliente_id != pedido.cliente_id
    ):
        return redirect(_inicio_por_rol(request.user))
    if pedido.estado == Pedido.ESTADO_CANCELADO:
        messages.error(request, 'No se pueden agregar productos a un pedido cancelado')
        return redirect('/pedidos/')

    productos = Producto.objects.all()
    detalles = DetallePedido.objects.filter(pedido=pedido)

    if request.method == 'POST':
        try:
            producto_id = int(request.POST.get('producto', ''))
            cantidad = int(request.POST.get('cantidad', ''))
        except (TypeError, ValueError):
            messages.error(request, 'Selecciona un producto e ingresa una cantidad entera')
            return redirect(f'/agregar-productos/{pedido.id}/')

        if cantidad < 1:
            messages.error(request, 'La cantidad debe ser un número entero mayor que cero')
            return redirect(f'/agregar-productos/{pedido.id}/')

        try:
            with transaction.atomic():
                producto = Producto.objects.select_for_update().get(pk=producto_id)
                if producto.stock < cantidad:
                    messages.error(request, 'Stock insuficiente para esa cantidad')
                    return redirect(f'/agregar-productos/{pedido.id}/')

                detalle, creado = DetallePedido.objects.get_or_create(
                    pedido=pedido,
                    producto=producto,
                    defaults={'cantidad': cantidad, 'precio': producto.precio},
                )
                if not creado:
                    detalle.cantidad += cantidad
                    detalle.precio = producto.precio
                    detalle.save(update_fields=['cantidad', 'precio'])

                producto.stock -= cantidad
                producto.save(update_fields=['stock'])
        except Producto.DoesNotExist:
            messages.error(request, 'El producto seleccionado ya no existe')
            return redirect(f'/agregar-productos/{pedido.id}/')

        messages.success(request, "Producto agregado correctamente")
        return redirect(f'/agregar-productos/{pedido.id}/')

    return render(request, 'agregar_productos.html', {
        'pedido': pedido,
        'productos': productos,
        'detalles': detalles
    })


@login_required
@require_POST
def cancelar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    if not es_admin(request.user) and (
        not es_cliente(request.user)
        or perfil_usuario(request.user).cliente_id != pedido.cliente_id
    ):
        return redirect(_inicio_por_rol(request.user))
    if pedido.estado == Pedido.ESTADO_CANCELADO:
        messages.info(request, 'Este pedido ya estaba cancelado')
        return redirect('/pedidos/')

    with transaction.atomic():
        for detalle in DetallePedido.objects.filter(pedido=pedido).select_related('producto'):
            producto = Producto.objects.select_for_update().get(pk=detalle.producto_id)
            producto.stock += detalle.cantidad
            producto.save(update_fields=['stock'])
        pedido.estado = Pedido.ESTADO_CANCELADO
        pedido.save(update_fields=['estado'])

    messages.success(request, f'El pedido #{pedido.id} se canceló y el stock fue restaurado')
    return redirect('/pedidos/')


def login_view(request):

    if request.user.is_authenticated:
        return redirect(_inicio_por_rol(request.user))

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            return redirect(_inicio_por_rol(user))
        else:
            return render(request, 'login.html', {
                'error': 'Usuario o contraseña incorrectos'
            })

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('/login/')

@login_required
def dashboard(request):
    if not es_admin(request.user):
        return redirect(_inicio_por_rol(request.user))

    total_clientes = Cliente.objects.count()
    total_productos = Producto.objects.count()
    pedidos_activos = Pedido.objects.exclude(estado=Pedido.ESTADO_CANCELADO)
    total_pedidos = pedidos_activos.count()

    ingresos = sum(p.total() for p in pedidos_activos)

    top_productos = list(
    DetallePedido.objects
    .filter(pedido__estado=Pedido.ESTADO_PENDIENTE)
    .values(nombre=F('producto__nombre'))
    .annotate(total=Sum('cantidad'))
    .order_by('-total')[:5]
)
    ultimos_pedidos = Pedido.objects.order_by('-id')[:5]

    context = {
        'clientes': total_clientes,
        'productos': total_productos,
        'pedidos': total_pedidos,
        'ingresos': ingresos,
        'top_productos': top_productos,
        'ultimos_pedidos': ultimos_pedidos,
    }

    return render(request, 'dashboard.html', context)