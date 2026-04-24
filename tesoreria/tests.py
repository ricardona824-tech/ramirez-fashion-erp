from django.test import TestCase, Client
from django.urls import reverse
from tesoreria.models import Cuenta, Movimiento


class TesoreriaTest(TestCase):
    def setUp(self):
        """Configuración inicial para las pruebas de Tesorería."""
        self.client = Client()
        # Creamos una cuenta con dinero y otra vacía
        self.cuenta_origen = Cuenta.objects.create(nombre="Caja Principal", tipo='EFECTIVO', saldo_actual=100000)
        self.cuenta_destino = Cuenta.objects.create(nombre="Banco Ahorros", tipo='BANCO', saldo_actual=0)

    def test_transferencia_exitosa(self):
        """Prueba: Transferir dinero resta de una cuenta y suma en la otra exactamente."""
        url = reverse('tesoreria:registrar_transferencia')
        # Simulamos una transferencia de $40.000
        response = self.client.post(url, {
            'cuenta_origen': self.cuenta_origen.id,
            'cuenta_destino': self.cuenta_destino.id,
            'monto': 40000,
            'concepto': 'Traslado de fondos'
        })

        self.cuenta_origen.refresh_from_db()
        self.cuenta_destino.refresh_from_db()

        # Matemáticas: 100k - 40k = 60k en origen. 0 + 40k = 40k en destino.
        self.assertEqual(self.cuenta_origen.saldo_actual, 60000)
        self.assertEqual(self.cuenta_destino.saldo_actual, 40000)

        # Verificar que se crearon los dos movimientos contables (Egreso e Ingreso)
        movimientos = Movimiento.objects.all()
        self.assertEqual(movimientos.count(), 2)

    def test_gasto_operativo_exitoso(self):
        """Prueba: Registrar un gasto descuenta el dinero y crea el registro."""
        url = reverse('tesoreria:registrar_gasto')
        # Simulamos un gasto de $30.000
        response = self.client.post(url, {
            'cuenta_origen': self.cuenta_origen.id,
            'monto': 30000,
            'categoria': 'Logística',
            'descripcion': 'Pago de transporte'
        })

        self.cuenta_origen.refresh_from_db()

        # Matemáticas: 100k - 30k = 70k
        self.assertEqual(self.cuenta_origen.saldo_actual, 70000)
