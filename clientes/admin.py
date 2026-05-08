from django.contrib import admin
from .models import Cliente, Pedido, Proveedor

# Registramos los modelos para poder gestionarlos
admin.site.register(Cliente)
admin.site.register(Pedido)
@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'saldo_a_favor')
    search_fields = ('nombre',)