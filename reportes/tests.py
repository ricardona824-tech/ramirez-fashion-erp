from django.test import TestCase, Client
from django.urls import reverse
from clientes.models import Cliente, Pedido
from tesoreria.models import Cuenta
from cartera.models import Credito


class ReportesTest(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Simulamos Tesorería ($50.000 en banco)
        Cuenta.objects.create(nombre="Banco", tipo='BANCO', saldo_actual=50000)

        # 2. Simulamos un cliente y un pedido ENTREGADO (Costo 80k, Venta 120k)
        cliente = Cliente.objects.create(nombre="Pedro Reportes")
        Pedido.objects.create(
            cliente=cliente, producto="Pantalón", proveedor="Prov",
            precio_costo=80000, precio_venta=120000, estado='ENTREGADO'
        )

        # 3. Simulamos Cartera (Alguien debe $40.000)
        Credito.objects.create(
            cliente=cliente, monto_total=40000, saldo_pendiente=40000, estado='ACTIVO'
        )

    def test_matematicas_dashboard_gerencial(self):
        """Prueba: El dashboard debe sumar correctamente las ganancias, tesorería y cartera."""
        url = reverse('reportes:dashboard_gerencial')
        response = self.client.get(url)

        # Obtenemos los números que la vista calculó
        utilidad_bruta = response.context['utilidad_bruta']
        total_tesoreria = response.context['total_tesoreria']
        total_cartera = response.context['total_cartera']

        # Matemáticas: 120k (Venta) - 80k (Costo) = 40.000
        self.assertEqual(utilidad_bruta, 40000)
        self.assertEqual(total_tesoreria, 50000)
        self.assertEqual(total_cartera, 40000)
