from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages
from .models import Cliente, Pedido
from .forms import ClienteForm, PedidoForm
from django.db import transaction
from tesoreria.models import Cuenta, Movimiento
from cartera.models import Credito
from .forms import ClienteForm, PedidoForm, PagarProveedorForm, CobrarClienteForm
from .forms import CancelarVentaForm


def lista_clientes(request):
    """Vista para listar y buscar clientes (HU 01)."""
    query = request.GET.get('q', '')
    if query:
        clientes = Cliente.objects.filter(
            Q(nombre__icontains=query) | Q(whatsapp__icontains=query)
        )
    else:
        clientes = Cliente.objects.all()

    context = {'clientes': clientes, 'query': query}
    return render(request, 'clientes/lista_clientes.html', context)


def crear_cliente(request):
    """Vista para registrar un nuevo cliente."""
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('clientes:lista_clientes')  # Redirige al listado tras guardar
    else:
        form = ClienteForm()

    return render(request, 'clientes/cliente_form.html', {'form': form, 'accion': 'Nuevo'})


def editar_cliente(request, pk):
    """Vista para actualizar datos de un cliente existente."""
    cliente = get_object_or_404(Cliente, pk=pk)  # Busca el cliente por su ID (Primary Key)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('clientes:lista_clientes')
    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'clientes/cliente_form.html', {'form': form, 'accion': 'Editar'})


def lista_pedidos(request):
    """Vista para ver todos los pedidos y su estado."""
    pedidos = Pedido.objects.all().select_related('cliente')  # select_related optimiza la consulta FK
    return render(request, 'clientes/lista_pedidos.html', {'pedidos': pedidos})


def crear_pedido(request):
    """Vista para ingresar un pedido nuevo (HU 02)."""
    if request.method == 'POST':
        form = PedidoForm(request.POST)
        if form.is_valid():
            form.save()  # El estado "PENDIENTE" y el ID se asignan solos
            return redirect('clientes:lista_pedidos')
    else:
        form = PedidoForm()

    return render(request, 'clientes/pedido_form.html', {'form': form})


def gestion_separacion(request):
    """Vista para gestionar pedidos con proveedores (HU 03)."""
    # 1. Obtener lista de proveedores únicos que tienen pedidos pendientes
    proveedores = Pedido.objects.filter(estado='PENDIENTE').values_list('proveedor', flat=True).distinct()

    # 2. Filtrar pedidos si se seleccionó un proveedor
    proveedor_seleccionado = request.GET.get('proveedor', '')
    pedidos = Pedido.objects.filter(estado='PENDIENTE')  # Solo mostramos los pendientes

    if proveedor_seleccionado:
        pedidos = pedidos.filter(proveedor=proveedor_seleccionado)

    # 3. Procesar las acciones masivas (POST)
    if request.method == 'POST':
        pedidos_ids = request.POST.getlist('pedidos_seleccionados')  # Lista de IDs de los checkboxes
        accion = request.POST.get('accion')  # Saber qué botón presionaron

        if pedidos_ids and accion:
            if accion == 'separar':
                Pedido.objects.filter(id_pedido__in=pedidos_ids).update(estado='SEPARADO')
            elif accion == 'agotar':
                Pedido.objects.filter(id_pedido__in=pedidos_ids).update(estado='AGOTADO')

            return redirect('clientes:gestion_separacion')

    context = {
        'pedidos': pedidos,
        'proveedores': proveedores,
        'proveedor_seleccionado': proveedor_seleccionado
    }
    return render(request, 'clientes/gestion_separacion.html', context)


def marcar_recogido(request, pk):
    """Vista para marcar pedido como RECOGIDO y registrar el egreso (HU 05)."""
    pedido = get_object_or_404(Pedido, pk=pk)

    # Validación de seguridad: Solo pedidos SEPARADOS se pueden recoger
    if pedido.estado != 'SEPARADO':
        return redirect('clientes:lista_pedidos')

    if request.method == 'POST':
        form = PagarProveedorForm(request.POST)
        if form.is_valid():
            cuenta = form.cleaned_data['cuenta_origen']

            # 👇 NUEVA VALIDACIÓN: Bloqueamos si no hay dinero suficiente 👇
            if cuenta.saldo_actual < pedido.precio_costo:
                messages.error(request,
                               f"¡Error! Saldo insuficiente en {cuenta.nombre}. Necesitas ${int(pedido.precio_costo):,} y solo tienes ${int(cuenta.saldo_actual):,}.")
            else:
                # transaction.atomic garantiza que los 3 pasos se cumplan
                with transaction.atomic():
                    # 1. Cambiar estado del pedido
                    pedido.estado = 'RECOGIDO'
                    pedido.save()

                    # 2. Restar el dinero de la cuenta (Precio Costo)
                    cuenta.saldo_actual -= pedido.precio_costo
                    cuenta.save()

                    # 3. Registrar el log de auditoría (Egreso)
                    Movimiento.objects.create(
                        cuenta=cuenta,
                        tipo='EGRESO',
                        monto=pedido.precio_costo,
                        concepto=f"Pago a {pedido.proveedor} por {pedido.producto}",
                        referencia_pedido=str(pedido.id_pedido)
                    )
                messages.success(request,
                                 f"Pago registrado correctamente. Se descontaron ${int(pedido.precio_costo):,} de {cuenta.nombre}.")
                return redirect('clientes:lista_pedidos')
    else:
        form = PagarProveedorForm()

    return render(request, 'clientes/recoger_pedido.html', {'form': form, 'pedido': pedido})


def entregar_pedido(request, pk):
    """Vista para entregar pedido y cobrar o enviar a cartera (HU 08)."""
    pedido = get_object_or_404(Pedido, pk=pk)

    if pedido.estado != 'RECOGIDO':
        return redirect('clientes:lista_pedidos')

    if request.method == 'POST':
        form = CobrarClienteForm(request.POST)
        if form.is_valid():
            tipo_pago = form.cleaned_data['tipo_pago']

            with transaction.atomic():
                # 1. Siempre marcamos el pedido como entregado
                pedido.estado = 'ENTREGADO'
                pedido.save()

                if tipo_pago == 'CONTADO':
                    # LÓGICA DE CONTADO (Entra a tesorería)
                    cuenta = form.cleaned_data['cuenta_destino']
                    cuenta.saldo_actual += pedido.precio_venta
                    cuenta.save()

                    Movimiento.objects.create(
                        cuenta=cuenta, tipo='INGRESO', monto=pedido.precio_venta,
                        concepto=f"Venta entregada a {pedido.cliente.nombre} - {pedido.producto}",
                        referencia_pedido=str(pedido.id_pedido)
                    )
                    mensaje = f"¡Venta exitosa! Ingresaron ${int(pedido.precio_venta):,} a {cuenta.nombre}."

                elif tipo_pago == 'CREDITO':
                    # LÓGICA DE CRÉDITO (Se va para Cartera)
                    Credito.objects.create(
                        cliente=pedido.cliente,
                        pedido=pedido, # Vinculamos el crédito a este pedido exacto
                        monto_total=pedido.precio_venta,
                        saldo_pendiente=pedido.precio_venta,
                        estado='ACTIVO'
                    )
                    mensaje = f"Pedido entregado. Se generó una deuda de ${int(pedido.precio_venta):,} a nombre de {pedido.cliente.nombre} en Cartera."

            messages.success(request, mensaje)
            return redirect('clientes:lista_pedidos')
    else:
        form = CobrarClienteForm()

    return render(request, 'clientes/entregar_pedido.html', {'form': form, 'pedido': pedido})


def solicitar_cambio(request, pk):
    """Inicia el proceso de cambio de prenda (ENTREGADO -> DEV_RECOGER)."""
    pedido = get_object_or_404(Pedido, pk=pk)
    if pedido.estado == 'ENTREGADO':
        pedido.estado = 'DEV_RECOGER'
        pedido.save()
        messages.warning(request, f"Se solicitó cambio para el pedido de {pedido.cliente.nombre}. Mensajero debe recogerlo.")
    return redirect('clientes:lista_pedidos')


def marcar_recogido_cliente(request, pk):
    """El mensajero recogió la prenda del cliente (DEV_RECOGER -> DEV_PROVEEDOR)."""
    pedido = get_object_or_404(Pedido, pk=pk)
    if pedido.estado == 'DEV_RECOGER':
        pedido.estado = 'DEV_PROVEEDOR'
        pedido.save()
        messages.info(request, "Prenda recogida. Pendiente ir al proveedor a realizar el cambio.")
    return redirect('clientes:lista_pedidos')


def marcar_cambiado_proveedor(request, pk):
    """Se hizo el cambio en el proveedor (DEV_PROVEEDOR -> DEV_ENTREGAR)."""
    pedido = get_object_or_404(Pedido, pk=pk)
    if pedido.estado == 'DEV_PROVEEDOR':
        pedido.estado = 'DEV_ENTREGAR'
        pedido.save()
        messages.info(request, "Cambio exitoso en el proveedor. Pendiente entregarle la nueva prenda al cliente.")
    return redirect('clientes:lista_pedidos')


def entregar_cambio(request, pk):
    """Se entrega la nueva prenda al cliente, cerrando el ciclo (DEV_ENTREGAR -> ENTREGADO)."""
    pedido = get_object_or_404(Pedido, pk=pk)
    if pedido.estado == 'DEV_ENTREGAR':
        pedido.estado = 'ENTREGADO'
        pedido.save()
        messages.success(request, "¡Cambio finalizado con éxito! La nueva prenda fue entregada al cliente.")
    return redirect('clientes:lista_pedidos')


def cancelar_venta(request, pk):
    """Cancela la venta, devuelve el costo y reembolsa al cliente (Camino B)."""
    pedido = get_object_or_404(Pedido, pk=pk)

    if request.method == 'POST':
        form = CancelarVentaForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # 1. Cambiar estado a CANCELADO
                pedido.estado = 'CANCELADO'
                pedido.save()

                # 2. PROVEEDOR: Devolvemos la prenda y nos devuelve el dinero (Costo)
                cuenta_prov = form.cleaned_data['cuenta_proveedor']
                cuenta_prov.saldo_actual += pedido.precio_costo
                cuenta_prov.save()
                Movimiento.objects.create(
                    cuenta=cuenta_prov, tipo='INGRESO', monto=pedido.precio_costo,
                    concepto=f"Reembolso de proveedor por devolución - {pedido.producto}",
                    referencia_pedido=str(pedido.id_pedido)
                )

                # 3. CLIENTE: Devolvemos el dinero o anulamos la deuda (Venta)
                tipo_reembolso = form.cleaned_data['tipo_reembolso_cliente']
                if tipo_reembolso == 'CONTADO':
                    cuenta_cli = form.cleaned_data['cuenta_cliente']
                    cuenta_cli.refresh_from_db()
                    cuenta_cli.saldo_actual -= pedido.precio_venta
                    cuenta_cli.save()
                    Movimiento.objects.create(
                        cuenta=cuenta_cli, tipo='EGRESO', monto=pedido.precio_venta,
                        concepto=f"Reembolso a cliente por devolución - {pedido.producto}",
                        referencia_pedido=str(pedido.id_pedido)
                    )
                elif tipo_reembolso == 'CREDITO':
                    # Buscamos la deuda en cartera y la anulamos
                    credito = Credito.objects.filter(pedido=pedido, estado='ACTIVO').first()
                    if credito:
                        credito.saldo_pendiente = 0
                        credito.estado = 'PAGADO'  # Se cierra la deuda
                        credito.save()

            messages.success(request, "Venta cancelada exitosamente. Contabilidad y Cartera actualizadas.")
            return redirect('clientes:lista_pedidos')
    else:
        form = CancelarVentaForm()

    return render(request, 'clientes/cancelar_venta.html', {'form': form, 'pedido': pedido})


def editar_pedido(request, id_pedido):
    """Permite editar un pedido existente."""
    # 1. Buscamos el pedido en la base de datos
    pedido = get_object_or_404(Pedido, pk=id_pedido)

    if request.method == 'POST':
        # 2. Le pasamos los nuevos datos (request.POST) y le decimos que sobreescriba este pedido (instance=pedido)
        form = PedidoForm(request.POST, instance=pedido)
        if form.is_valid():
            form.save()
            messages.success(request, "¡Pedido actualizado correctamente!")
            return redirect('clientes:lista_pedidos')
    else:
        # 3. Si apenas entra a la página, le mostramos el formulario prellenado
        form = PedidoForm(instance=pedido)

    # Nota: Asegúrate de que 'clientes/pedido_form.html' sea el mismo archivo que usas para CREAR pedidos
    return render(request, 'clientes/pedido_form.html', {
        'form': form,
        'titulo': f'Editar Pedido - {pedido.cliente.nombre}'
    })