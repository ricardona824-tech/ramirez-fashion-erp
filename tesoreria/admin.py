from django.contrib import admin
from .models import Cuenta, Gasto

# Esta forma de registrarlo hace que la tabla se vea mucho más profesional
@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'saldo_actual')
    list_filter = ('tipo',)
    search_fields = ('nombre',)

@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ('categoria', 'monto', 'fecha') # Cambia por tus nombres reales
