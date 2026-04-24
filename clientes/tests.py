from django.test import TestCase, Client
from django.urls import reverse
from tesoreria.models import Cuenta, Movimiento
from clientes.models import Cliente, Pedido


class FlujoVentasTest(TestCase):
    def setUp(self):
        """Configuración de los datos de prueba."""
        self.client = Client()
        self.cliente = Cliente.objects.create(nombre="Juan Prueba")

        # Creamos dos cuentas: una sin dinero para probar errores y una con dinero para el flujo normal
        self.cuenta_pobre = Cuenta.objects.create(nombre="Banco Pobre", tipo='BANCO', saldo_actual=50000)
        self.cuenta_rica = Cuenta.objects.create(nombre="Banco Rico", tipo='BANCO', saldo_actual=200000)

        # Pedido 1: Para probar que no pague sin fondos
        self.pedido_separado = Pedido.objects.create(
            cliente=self.cliente, producto="Camisa 1", proveedor="Prov",
            precio_costo=80000, precio_venta=120000, estado='SEPARADO'
        )

        # Pedido 2: Para probar la entrega exitosa
        self.pedido_recogido = Pedido.objects.create(
            cliente=self.cliente, producto="Camisa 2", proveedor="Prov",
            precio_costo=80000, precio_venta=120000, estado='RECOGIDO'
        )

        # Pedido 3: Para probar la cancelación y reembolso
        self.pedido_entregado = Pedido.objects.create(
            cliente=self.cliente, producto="Camisa 3", proveedor="Prov",
            precio_costo=80000, precio_venta=120000, estado='ENTREGADO'
        )

    def test_1_evitar_saldo_negativo(self):
        """Prueba: Bloquear pago a proveedor si no hay fondos."""
        url = reverse('clientes:marcar_recogido', args=[self.pedido_separado.id_pedido])
        response = self.client.post(url, {'cuenta_origen': self.cuenta_pobre.id})

        self.pedido_separado.refresh_from_db()
        self.assertEqual(self.pedido_separado.estado, 'SEPARADO')  # No debió avanzar

    def test_2_flujo_feliz_entrega_contado(self):
        """Prueba: Entregar pedido de contado suma el dinero al banco."""
        url = reverse('clientes:entregar_pedido', args=[self.pedido_recogido.id_pedido])
        # Simulamos que cobra de contado y entra al Banco Rico
        response = self.client.post(url, {
            'tipo_pago': 'CONTADO',
            'cuenta_destino': self.cuenta_rica.id
        })

        self.pedido_recogido.refresh_from_db()
        self.cuenta_rica.refresh_from_db()

        self.assertEqual(self.pedido_recogido.estado, 'ENTREGADO')
        # 200,000 que tenía + 120,000 de la venta = 320,000
        self.assertEqual(self.cuenta_rica.saldo_actual, 320000)

    def test_3_cancelar_venta_devuelve_saldos(self):
        """Prueba: Cancelar venta reintegra el costo del proveedor y saca el reembolso del cliente."""
        url = reverse('clientes:cancelar_venta', args=[self.pedido_entregado.id_pedido])
        response = self.client.post(url, {
            'cuenta_proveedor': self.cuenta_rica.id,
            'tipo_reembolso_cliente': 'CONTADO',
            'cuenta_cliente': self.cuenta_rica.id
        })

        self.pedido_entregado.refresh_from_db()
        self.cuenta_rica.refresh_from_db()

        self.assertEqual(self.pedido_entregado.estado, 'CANCELADO')
        # Matemáticas: 200,000 (Inicial) + 80,000 (Costo Devuelto) - 120,000 (Reembolso) = 160,000
        self.assertEqual(self.cuenta_rica.saldo_actual, 160000)