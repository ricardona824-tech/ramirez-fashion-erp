from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    path('', views.lista_clientes, name='lista_clientes'),
    path('nuevo/', views.crear_cliente, name='crear_cliente'),
    path('editar/<int:pk>/', views.editar_cliente, name='editar_cliente'),
    path('pedidos/', views.lista_pedidos, name='lista_pedidos'),
    path('pedidos/nuevo/', views.crear_pedido, name='crear_pedido'),
    path('separacion/', views.gestion_separacion, name='gestion_separacion'),
    path('pedidos/recoger/<uuid:pk>/', views.marcar_recogido, name='marcar_recogido'),
    path('pedidos/entregar/<uuid:pk>/', views.entregar_pedido, name='entregar_pedido'),
    path('pedidos/cambio/solicitar/<uuid:pk>/', views.solicitar_cambio, name='solicitar_cambio'),
    path('pedidos/cambio/recogido/<uuid:pk>/', views.marcar_recogido_cliente, name='marcar_recogido_cliente'),
    path('pedidos/cambio/proveedor/<uuid:pk>/', views.marcar_cambiado_proveedor, name='marcar_cambiado_proveedor'),
    path('pedidos/cambio/entregar/<uuid:pk>/', views.entregar_cambio, name='entregar_cambio'),
    path('pedidos/cancelar/<uuid:pk>/', views.cancelar_venta, name='cancelar_venta'),
    path('pedidos/editar/<uuid:id_pedido>/', views.editar_pedido, name='editar_pedido'),
]