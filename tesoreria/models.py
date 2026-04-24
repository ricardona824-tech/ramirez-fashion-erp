from django.db import models
from django.utils import timezone


class Cuenta(models.Model):
    """
    Modelo para las cuentas de tesorería (HU 04).
    Almacena los saldos de Efectivo, Banco 1, Banco 2, etc.
    """
    TIPOS_CUENTA = [
        ('EFECTIVO', 'Efectivo'),
        ('BANCO', 'Banco'),
    ]
    nombre = models.CharField(max_length=50, unique=True, verbose_name="Nombre de la Cuenta")
    tipo = models.CharField(max_length=20, choices=TIPOS_CUENTA, default='BANCO')

    # Manejamos los valores únicamente en Pesos Colombianos (COP)
    saldo_actual = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name="Saldo Actual (COP)")

    class Meta:
        verbose_name = "Cuenta de Tesorería"
        verbose_name_plural = "Cuentas de Tesorería"
        ordering = ['nombre']

    def __str__(self):
        saldo_formateado = f"{int(self.saldo_actual):,}".replace(',', '.')
        return f"{self.nombre} - Saldo: ${saldo_formateado}"


class Movimiento(models.Model):
    """
    Modelo para registrar logs de auditoría por cada movimiento de dinero.
    Será vital para Egresos (HU 05) e Ingresos.
    """
    TIPOS_MOVIMIENTO = [
        ('INGRESO', 'Ingreso'),
        ('EGRESO', 'Egreso'),
    ]
    cuenta = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=10, choices=TIPOS_MOVIMIENTO)
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Monto (COP)")
    concepto = models.CharField(max_length=255, verbose_name="Concepto / Descripción")
    fecha = models.DateTimeField(auto_now_add=True)

    # Dejamos un campo de referencia para vincularlo al ID del Pedido más adelante
    referencia_pedido = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID Pedido Referencia")

    class Meta:
        verbose_name = "Movimiento"
        verbose_name_plural = "Movimientos"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.tipo} - ${self.monto} en {self.cuenta.nombre}"


class Gasto(models.Model):
    cuenta = models.ForeignKey('Cuenta', on_delete=models.PROTECT)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255)

    # El reloj automático del gasto
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.categoria} - ${self.monto} ({self.fecha.strftime('%Y-%m-%d')})"


