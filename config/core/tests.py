from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Cliente, DetallePedido, Pedido, Producto, Perfil, Proveedor, RecepcionMercancia


class PedidoValidationTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='tester', password='test-password')
		self.cliente = Cliente.objects.create(
			nombre='Cliente de prueba',
			telefono='555-0101',
			direccion='Calle de prueba 10',
			documento_identidad='DOC-555-0101',
		)
		self.user.perfil.cliente = self.cliente
		self.user.perfil.save(update_fields=['cliente'])
		self.proveedor = Proveedor.objects.create(
			nombre='Proveedor de prueba',
			documento_fiscal='TAX-TEST-1',
		)
		self.producto = Producto.objects.create(
			nombre='Teclado de prueba',
			precio='49.90',
			stock=5,
		)
		self.pedido = Pedido.objects.create(cliente=self.cliente, usuario=self.user)
		self.url = f'/agregar-productos/{self.pedido.id}/'
		self.client.force_login(self.user)

	def test_cantidad_invalida_no_modifica_el_inventario(self):
		for cantidad in ('', '0', '-2', 'dos'):
			with self.subTest(cantidad=cantidad):
				response = self.client.post(self.url, {'producto': self.producto.id, 'cantidad': cantidad})

				self.assertRedirects(response, self.url)

		self.producto.refresh_from_db()
		self.assertEqual(self.producto.stock, 5)
		self.assertFalse(DetallePedido.objects.filter(pedido=self.pedido).exists())

	def test_stock_se_descuenta_una_sola_vez_y_acumula_el_detalle(self):
		self.client.post(self.url, {'producto': self.producto.id, 'cantidad': '2'})
		self.client.post(self.url, {'producto': self.producto.id, 'cantidad': '1'})

		self.producto.refresh_from_db()
		detalle = DetallePedido.objects.get(pedido=self.pedido, producto=self.producto)
		self.assertEqual(self.producto.stock, 2)
		self.assertEqual(detalle.cantidad, 3)

	def test_cantidad_mayor_al_stock_no_se_agrega(self):
		response = self.client.post(self.url, {'producto': self.producto.id, 'cantidad': '6'})

		self.assertRedirects(response, self.url)
		self.producto.refresh_from_db()
		self.assertEqual(self.producto.stock, 5)
		self.assertFalse(DetallePedido.objects.filter(pedido=self.pedido).exists())

	def test_las_pantallas_de_gestion_se_renderizan(self):
		self.user.perfil.tipo_usuario = 'admin'
		self.user.perfil.save(update_fields=['tipo_usuario'])

		urls = [
			'/clientes/',
			'/crear-cliente/',
			f'/editar-cliente/{self.cliente.id}/',
			'/productos/',
			'/crear-producto/',
			f'/editar-producto/{self.producto.id}/',
			'/pedidos/',
			'/crear-pedido/',
			self.url,
			'/usuarios/',
			'/crear-usuario/',
			'/proveedores/',
			'/crear-proveedor/',
			f'/editar-proveedor/{self.proveedor.id}/',
			'/recepciones/',
			'/registrar-recepcion/',
		]
		for url in urls:
			with self.subTest(url=url):
				self.assertEqual(self.client.get(url).status_code, 200)

	def test_documento_legal_es_obligatorio_y_unico(self):
		self.user.perfil.tipo_usuario = 'admin'
		self.user.perfil.save(update_fields=['tipo_usuario'])
		url = '/crear-cliente/'
		datos = {
			'nombre': 'Otro cliente',
			'telefono': '555-0102',
			'direccion': 'Calle nueva 12',
		}

		respuesta_sin_documento = self.client.post(url, datos)
		self.assertContains(respuesta_sin_documento, 'El documento de identidad es obligatorio')

		respuesta_duplicada = self.client.post(url, {
			**datos,
			'documento_identidad': self.cliente.documento_identidad,
		})
		self.assertContains(respuesta_duplicada, 'Ya existe un cliente con ese documento de identidad')
		self.assertEqual(Cliente.objects.count(), 1)

		respuesta_direccion_vacia = self.client.post(url, {
			**datos,
			'direccion': '',
			'documento_identidad': 'DOC-555-0102',
		})
		self.assertContains(respuesta_direccion_vacia, 'La dirección del cliente es obligatoria')

		respuesta_valida = self.client.post(url, {
			**datos,
			'documento_identidad': 'DOC-555-0102',
		})
		self.assertRedirects(respuesta_valida, '/clientes/')
		self.assertEqual(Cliente.objects.count(), 2)

	def test_admin_crea_cuentas_cliente_y_proveedor_vinculadas(self):
		self.user.perfil.tipo_usuario = Perfil.ROL_ADMIN
		self.user.perfil.save(update_fields=['tipo_usuario'])
		password = 'Secure-Account-Pass!2026'
		cliente_response = self.client.post('/crear-cliente/', {
			'nombre': 'Cliente nuevo',
			'telefono': '555-0199',
			'direccion': 'Avenida 12',
			'documento_identidad': 'DOC-0199',
			'crear_cuenta': 'on',
			'username': 'cliente_nuevo',
			'email': 'cliente@example.test',
			'password': password,
			'password_confirmation': password,
		})
		self.assertRedirects(cliente_response, '/clientes/')
		cuenta_cliente = User.objects.get(username='cliente_nuevo')
		cliente_nuevo = Cliente.objects.get(documento_identidad='DOC-0199')
		self.assertEqual(cuenta_cliente.perfil.cliente, cliente_nuevo)
		self.assertEqual(cuenta_cliente.perfil.tipo_usuario, Perfil.ROL_CLIENTE)
		self.assertEqual(cuenta_cliente.email, 'cliente@example.test')
		self.assertTrue(cuenta_cliente.check_password(password))

		proveedor_password = 'Secure-Supplier-Pass!2026'
		proveedor_response = self.client.post('/crear-proveedor/', {
			'nombre': 'Proveedor nuevo',
			'documento_fiscal': 'TAX-NEW-1',
			'correo': 'proveedor@example.test',
			'crear_cuenta': 'on',
			'username': 'proveedor_nuevo',
			'password': proveedor_password,
			'password_confirmation': proveedor_password,
		})
		self.assertRedirects(proveedor_response, '/proveedores/')
		cuenta_proveedor = User.objects.get(username='proveedor_nuevo')
		proveedor_nuevo = Proveedor.objects.get(documento_fiscal='TAX-NEW-1')
		self.assertEqual(cuenta_proveedor.perfil.proveedor, proveedor_nuevo)
		self.assertEqual(cuenta_proveedor.perfil.tipo_usuario, Perfil.ROL_PROVEEDOR)
		self.assertEqual(cuenta_proveedor.email, 'proveedor@example.test')
		self.assertTrue(cuenta_proveedor.check_password(proveedor_password))

		cuenta_simple_response = self.client.post('/crear-usuario/', {
			'username': 'cuenta_clave_simple',
			'tipo_usuario': Perfil.ROL_CLIENTE,
			'password': 'admin',
			'password_confirmation': 'admin',
		})
		self.assertRedirects(cuenta_simple_response, '/usuarios/')
		cuenta_admin = User.objects.get(username='cuenta_clave_simple')
		self.assertTrue(cuenta_admin.check_password('admin'))
		self.assertEqual(cuenta_admin.perfil.tipo_usuario, Perfil.ROL_ADMIN)

	def test_falla_al_crear_cuenta_no_deja_ficha_sin_cuenta(self):
		self.user.perfil.tipo_usuario = Perfil.ROL_ADMIN
		self.user.perfil.save(update_fields=['tipo_usuario'])

		response = self.client.post('/crear-cliente/', {
			'nombre': 'Cliente incompleto',
			'telefono': '555-0103',
			'direccion': 'Calle nueva 13',
			'documento_identidad': 'DOC-0103',
			'crear_cuenta': 'on',
			'username': 'cliente_incompleto',
			'password': 'correcta',
			'password_confirmation': 'distinta',
		})

		self.assertContains(response, 'Las contraseñas no coinciden')
		self.assertFalse(Cliente.objects.filter(documento_identidad='DOC-0103').exists())
		self.assertFalse(User.objects.filter(username='cliente_incompleto').exists())

	def test_crear_ficha_sin_cuenta_sigue_siendo_opcional(self):
		self.user.perfil.tipo_usuario = Perfil.ROL_ADMIN
		self.user.perfil.save(update_fields=['tipo_usuario'])

		response = self.client.post('/crear-proveedor/', {
			'nombre': 'Proveedor sin acceso',
			'documento_fiscal': 'TAX-NO-ACCOUNT',
		})

		self.assertRedirects(response, '/proveedores/')
		proveedor = Proveedor.objects.get(documento_fiscal='TAX-NO-ACCOUNT')
		self.assertFalse(Perfil.objects.filter(proveedor=proveedor).exists())

	def test_proveedor_registra_entrada_y_solo_accede_a_sus_vistas(self):
		perfil = self.user.perfil
		perfil.tipo_usuario = Perfil.ROL_PROVEEDOR
		perfil.cliente = None
		perfil.proveedor = self.proveedor
		perfil.save(update_fields=['tipo_usuario', 'cliente', 'proveedor'])

		response = self.client.post('/registrar-recepcion/', {
			'producto': str(self.producto.id),
			'cantidad': '3',
			'costo_unitario': '21.45',
			'observaciones': 'Entrega de prueba',
		})
		self.assertRedirects(response, '/recepciones/')
		self.producto.refresh_from_db()
		self.assertEqual(self.producto.stock, 8)
		recepcion = RecepcionMercancia.objects.get()
		self.assertEqual(recepcion.proveedor, self.proveedor)
		self.assertEqual(recepcion.cantidad, 3)
		self.assertEqual(recepcion.costo_unitario, Decimal('21.45'))

		self.assertEqual(self.client.get('/pedidos/').url, '/productos/')
		self.assertEqual(self.client.get('/recepciones/').status_code, 200)

	def test_cliente_solo_ve_sus_pedidos_y_cancelar_devuelve_stock(self):
		otro_cliente = Cliente.objects.create(
			nombre='Otro cliente',
			telefono='555-0198',
			direccion='Calle 2',
			documento_identidad='DOC-0198',
		)
		otro_pedido = Pedido.objects.create(cliente=otro_cliente)
		response = self.client.get('/pedidos/')
		self.assertEqual(list(response.context['pedidos']), [self.pedido])
		self.assertRedirects(self.client.get(f'/agregar-productos/{otro_pedido.id}/'), '/pedidos/')

		self.client.post(self.url, {'producto': self.producto.id, 'cantidad': '2'})
		cancel_response = self.client.post(f'/cancelar-pedido/{self.pedido.id}/')
		self.assertRedirects(cancel_response, '/pedidos/')
		self.producto.refresh_from_db()
		self.pedido.refresh_from_db()
		self.assertEqual(self.producto.stock, 5)
		self.assertEqual(self.pedido.estado, Pedido.ESTADO_CANCELADO)

		self.client.post(f'/cancelar-pedido/{self.pedido.id}/')
		self.producto.refresh_from_db()
		self.assertEqual(self.producto.stock, 5)

	def test_cliente_no_accede_a_gestion_administrativa(self):
		for url in ('/usuarios/', '/proveedores/', '/crear-producto/', '/dashboard/'):
			with self.subTest(url=url):
				self.assertRedirects(self.client.get(url), '/pedidos/')

		response = self.client.post('/crear-usuario/', {
			'username': 'cuenta_no_autorizada',
			'tipo_usuario': Perfil.ROL_ADMIN,
			'password': 'Secure-Account-Pass!2026',
			'password_confirmation': 'Secure-Account-Pass!2026',
		})
		self.assertRedirects(response, '/pedidos/')
		self.assertFalse(User.objects.filter(username='cuenta_no_autorizada').exists())
