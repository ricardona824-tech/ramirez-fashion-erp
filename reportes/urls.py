from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('', views.dashboard_gerencial, name='dashboard_gerencial'),
    path('estado-cuenta/', views.estado_cuenta_cliente, name='estado_cuenta_cliente'),
    path('resumen-cartera/', views.resumen_cartera, name='resumen_cartera'),
]