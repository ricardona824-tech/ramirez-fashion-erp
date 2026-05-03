import uuid
from django.db import models


class Cliente(models.Model):
    """
    Modelo para el Maestro de Clientes (HU 01).
    """
    # Campos solicitados en el Backlog
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Cliente")
    whatsapp = models.CharField(max_length=20, unique=True, verbose_name="WhatsApp")  # Único por cliente
    direccion = models.CharField(max_length=255, verbose_name="Dirección")
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad")

    # Fecha de creación automática para control interno
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} - {self.whatsapp}"


class Pedido(models.Model):
    """
    Modelo para el Registro de Pedido y Trazabilidad (HU 02 y HU 03).
    """
    # Estados del pedido definidos en el Backlog
    ESTADOS_PEDIDO = [
        ('PENDIENTE', 'Pendiente por Separar'),
        ('SEPARADO', 'Separado/Confirmado'),
        ('AGOTADO', 'Agotado'),
        ('RECOGIDO', 'Recogido'),
        ('ENTREGADO', 'Entregado'),
        ('DEV_RECOGER', 'Devolución: Recoger al cliente'),
        ('DEV_PROVEEDOR', 'Devolución: Cambiar en proveedor'),
        ('DEV_ENTREGAR', 'Devolución: Entregar al cliente'),
        ('CANCELADO', 'Venta Cancelada / Reembolsada'),
    ]

    # ID de pedido único, no visible en la UI principal
    id_pedido = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relación con el Cliente (FK)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='pedidos')

    # Detalles del Producto
    producto = models.CharField(max_length=255, verbose_name="Producto")
    talla = models.CharField(max_length=50, verbose_name="Talla")
    color = models.CharField(max_length=50, verbose_name="Color")
    proveedor = models.CharField(max_length=255, verbose_name="Proveedor")

    # Finanzas en Pesos Colombianos (COP)
    precio_costo = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Costo (COP)")
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Venta (COP)")

    # Trazabilidad
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_PEDIDO,
        default='PENDIENTE',  # Estado inicial automático
        verbose_name="Estado del Pedido"
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-fecha_registro']

    def __str__(self):
        return f"Pedido {self.id_pedido} - {self.producto} ({self.estado})"


    pagado_al_proveedor = models.BooleanField(default=False, verbose_name="¿Pagado al Proveedor?")
