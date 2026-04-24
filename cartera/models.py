from django.db import models
from clientes.models import Cliente, Pedido
from tesoreria.models import Cuenta


class Credito(models.Model):
    """Modelo para registrar la deuda total de un cliente (Fiado)."""
    ESTADOS = [
        ('ACTIVO', 'Activo (Con deuda)'),
        ('PAGADO', 'Pagado al 100%'),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='creditos')
    pedido = models.ForeignKey(Pedido, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Pedido asociado")

    monto_total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Monto Total de la Deuda")
    saldo_pendiente = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Saldo Pendiente")

    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVO')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Crédito / Fiado"
        verbose_name_plural = "Créditos y Fiados"
        ordering = ['-fecha_registro']

    def __str__(self):
        saldo_fmt = f"{int(self.saldo_pendiente):,}".replace(',', '.')
        return f"Deuda de {self.cliente.nombre} - Pendiente: ${saldo_fmt}"


class Abono(models.Model):
    """Modelo para registrar los pagos parciales a una deuda."""
    credito = models.ForeignKey(Credito, on_delete=models.CASCADE, related_name='abonos')
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Monto del Abono")
    cuenta_destino = models.ForeignKey(Cuenta, on_delete=models.PROTECT, verbose_name="Cuenta donde ingresa el dinero")

    fecha = models.DateTimeField(auto_now_add=True)
    comprobante = models.CharField(max_length=100, blank=True, null=True, verbose_name="N° Comprobante / Referencia")

    class Meta:
        verbose_name = "Abono"
        verbose_name_plural = "Abonos"
        ordering = ['-fecha']

    def __str__(self):
        monto_fmt = f"{int(self.monto):,}".replace(',', '.')
        return f"Abono de ${monto_fmt} a {self.credito.cliente.nombre}"
