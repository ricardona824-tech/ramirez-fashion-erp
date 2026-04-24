from django.contrib import admin
from .models import Cliente, Pedido

# Registramos los modelos para poder gestionarlos
admin.site.register(Cliente)
admin.site.register(Pedido)