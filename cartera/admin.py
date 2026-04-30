from django.contrib import admin
from .models import Credito, Abono

@admin.register(Credito)
class CreditoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'monto_total', 'saldo_pendiente', 'estado', 'fecha_registro')
    list_filter = ('estado',)
    search_fields = ('cliente__nombre',)

@admin.register(Abono)
class AbonoAdmin(admin.ModelAdmin):
    list_display = ('credito', 'monto', 'cuenta_destino', 'fecha')
    search_fields = ('credito__cliente__nombre',)
