from django.urls import path
from . import views

app_name = 'tesoreria'

urlpatterns = [
    # Ruta principal del módulo de finanzas
    path('', views.dashboard_tesoreria, name='dashboard'),
    path('gasto/', views.registrar_gasto, name='registrar_gasto'),
    path('transferencia/', views.registrar_transferencia, name='registrar_transferencia'),
]