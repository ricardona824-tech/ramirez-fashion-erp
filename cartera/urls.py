from django.urls import path
from . import views

app_name = 'cartera'

urlpatterns = [
    path('', views.lista_creditos, name='lista_creditos'),
    path('nuevo/', views.crear_credito, name='crear_credito'),
    path('abono/<int:pk>/', views.registrar_abono, name='registrar_abono'),
]