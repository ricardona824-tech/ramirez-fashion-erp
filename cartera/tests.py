from django.test import TestCase, Client
from django.urls import reverse
from tesoreria.models import Cuenta, Movimiento
from clientes.models import Cliente
from cartera.models import Credito, Abono


class CarteraTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.cuenta = Cuenta.objects.create(nombre="Caja Menor", tipo='EFECTIVO', saldo_actual=0)
        self.cliente = Cliente.objects.create(nombre="Maria Deudora")

        # Le creamos una deuda de 100.000
        self.credito = Credito.objects.create(
            cliente=self.cliente, monto_total=100000, saldo_pendiente=100000, estado='ACTIVO'
        )

    def test_abono_reduce_deuda_y_suma_tesoreria(self):
        """Prueba: Hacer un abono baja la deuda del cliente y sube la plata del banco."""
        url = reverse('cartera:registrar_abono', args=[self.credito.id])
        # Simulamos un abono de 40.000
        response = self.client.post(url, {
            'monto': 40000,
            'cuenta_destino': self.cuenta.id,
            'comprobante': 'Transferencia Nequi'
        })

        self.credito.refresh_from_db()
        self.cuenta.refresh_from_db()

        # Matemáticas: Deuda (100k - 40k = 60k). Banco (0 + 40k = 40k)
        self.assertEqual(self.credito.saldo_pendiente, 60000)
        self.assertEqual(self.cuenta.saldo_actual, 40000)

        # Verificamos que se creó el registro contable automáticamente
        self.assertTrue(Movimiento.objects.filter(cuenta=self.cuenta, monto=40000, tipo='INGRESO').exists())
