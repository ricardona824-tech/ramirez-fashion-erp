from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Ruta del panel de administración
    path('admin/', admin.site.urls),
    
    # Conectamos las rutas de nuestro módulo de clientes
    path('clientes/', include('clientes.urls')),
    path('tesoreria/', include('tesoreria.urls')),
    path('cartera/', include('cartera.urls')),
    path('reportes/', include('reportes.urls')),
]