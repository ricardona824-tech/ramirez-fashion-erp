from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages
from .models import Cliente, Pedido
from .forms import ClienteForm, PedidoForm, ProveedorForm
from django.db import transaction
from tesoreria.models import Cuenta, Movimiento
from cartera.models import Credito
from .forms import ClienteForm, PedidoForm, PagarProveedorForm, CobrarClienteForm
from .forms import CancelarVentaForm
from django.http import HttpResponse
from clientes.models import Proveedor, Pedido
from decimal import Decimal


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
    # BONUS DE VELOCIDAD: Agregamos 'proveedor_oficial' aquí para que Django no haga 100 consultas a la base de datos
    pedidos = Pedido.objects.select_related('cliente', 'proveedor_oficial').order_by('-fecha_registro')

    query = request.GET.get('q', '')

    if query:
        pedidos = pedidos.filter(
            Q(cliente__nombre__icontains=query) |
            Q(proveedor__icontains=query) |
            Q(proveedor_oficial__nombre__icontains=query) |  # ¡EL SUPERPODER DEL BUSCADOR!
            Q(producto__icontains=query)
        ).distinct()
    else:
        # 2. EL ARCHIVADO: Si la pantalla carga normal (sin buscar),
        # ocultamos los de la fecha de migración que ya están cerrados.
        pedidos = pedidos.exclude(
            fecha_registro__year=2026,
            fecha_registro__month=4,
            fecha_registro__day=30,
            estado__in=['ENTREGADO', 'CANCELADO']
        )

        # 3. LÍMITE DE PANTALLA: Solo mostramos los últimos 100 registros para que cargue en milisegundos.
        pedidos = pedidos[:100]

    return render(request, 'clientes/lista_pedidos.html', {
        'pedidos': pedidos,
        'query': query
    })


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


def registrar_pago_proveedor(request, id_pedido):
    pedido = get_object_or_404(Pedido, pk=id_pedido)

    if pedido.pagado_al_proveedor:
        messages.warning(request, "Este pedido ya fue pagado al proveedor.")
        return redirect('clientes:lista_pedidos')

    proveedor = pedido.proveedor_oficial
    # Aseguramos que el saldo disponible sea tipo Decimal
    saldo_disponible = proveedor.saldo_a_favor if proveedor else Decimal('0')

    if request.method == 'POST':
        form = PagarProveedorForm(request.POST)

        # 1. Obtenemos el valor del bono digitado y lo convertimos a Decimal de forma segura
        monto_bono_str = request.POST.get('monto_bono', '0')
        if not monto_bono_str:  # Por si envían el campo vacío
            monto_bono_str = '0'
        monto_bono_usar = Decimal(monto_bono_str)

        # 2. Calculamos el faltante con matemáticas exactas
        monto_faltante = pedido.precio_costo - monto_bono_usar

        # 3. Validaciones de seguridad
        if monto_bono_usar > saldo_disponible:
            messages.error(request, "No puedes usar más bono del que tienes disponible.")
        elif monto_bono_usar > pedido.precio_costo:
            messages.error(request, "El bono no puede ser mayor al costo del pedido.")
        else:
            # Si hay que pagar algo con dinero real...
            if monto_faltante > Decimal('0'):
                if form.is_valid():
                    cuenta = form.cleaned_data['cuenta_origen']
                    if cuenta.saldo_actual < monto_faltante:
                        messages.error(request, f"Saldo insuficiente en {cuenta.nombre} para cubrir el excedente.")
                        return render(request, 'clientes/pagar_proveedor.html',
                                      {'form': form, 'pedido': pedido, 'saldo_disponible': saldo_disponible})

                    with transaction.atomic():
                        # A. Descontar del bono (Perfil del proveedor y Tesorería)
                        if monto_bono_usar > Decimal('0'):
                            proveedor.saldo_a_favor -= monto_bono_usar
                            proveedor.save()

                            # Conexión con la cuenta BONOS Y AJUSTES
                            Cuenta = Movimiento._meta.get_field('cuenta').related_model
                            cuenta_bonos = Cuenta.objects.filter(nombre__icontains="BONOS").first()

                            if cuenta_bonos:
                                cuenta_bonos.saldo_actual -= monto_bono_usar
                                cuenta_bonos.save()
                                Movimiento.objects.create(
                                    cuenta=cuenta_bonos,
                                    tipo='EGRESO',
                                    monto=monto_bono_usar,
                                    concepto=f"Uso de bono para pago parcial - Proveedor: {proveedor.nombre}",
                                    referencia_pedido=str(pedido.id_pedido)
                                )

                        # B. Descontar de tesorería el excedente (Dinero real)
                        cuenta.saldo_actual -= monto_faltante
                        cuenta.save()

                        # C. Registro contable por el dinero real que salió
                        Movimiento.objects.create(
                            cuenta=cuenta, tipo='EGRESO', monto=monto_faltante,
                            concepto=f"Pago parcial a {proveedor.nombre} (Bono: ${int(monto_bono_usar)} | Efectivo: ${int(monto_faltante)})",
                            referencia_pedido=str(pedido.id_pedido)
                        )

                        pedido.pagado_al_proveedor = True
                        pedido.save()

                    messages.success(request,
                                     f"¡Pago exitoso! Se usaron ${int(monto_bono_usar):,} de bono y ${int(monto_faltante):,} de {cuenta.nombre}.")
                    return redirect('clientes:lista_pedidos')
            else:
                # El bono cubrió el 100% del pago
                with transaction.atomic():
                    proveedor.saldo_a_favor -= monto_bono_usar
                    proveedor.save()

                    # Conexión con la cuenta BONOS Y AJUSTES
                    Cuenta = Movimiento._meta.get_field('cuenta').related_model
                    cuenta_bonos = Cuenta.objects.filter(nombre__icontains="BONOS").first()

                    if cuenta_bonos:
                        cuenta_bonos.saldo_actual -= monto_bono_usar
                        cuenta_bonos.save()
                        Movimiento.objects.create(
                            cuenta=cuenta_bonos,
                            tipo='EGRESO',
                            monto=monto_bono_usar,
                            concepto=f"Uso de bono para pago total - Proveedor: {proveedor.nombre}",
                            referencia_pedido=str(pedido.id_pedido)
                        )

                    pedido.pagado_al_proveedor = True
                    pedido.save()

                messages.success(request, f"¡Pago exitoso! El bono cubrió el 100% del costo.")
                return redirect('clientes:lista_pedidos')

    else:
        form = PagarProveedorForm()

    return render(request, 'clientes/pagar_proveedor.html', {
        'form': form,
        'pedido': pedido,
        'saldo_disponible': saldo_disponible
    })


def marcar_recogido(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)

    # Ahora solo cambia el estado físico
    if pedido.estado == 'SEPARADO':
        pedido.estado = 'RECOGIDO'
        pedido.save()
        messages.success(request, f"El producto {pedido.producto} ahora está marcado como RECOGIDO.")

    return redirect('clientes:lista_pedidos')


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


def eliminar_pedido(request, pk):
    # Buscamos el pedido por su ID
    pedido = get_object_or_404(Pedido, pk=pk)

    # Si el usuario hace clic en el botón rojo de confirmación (POST)
    if request.method == 'POST':
        producto_nombre = pedido.producto
        pedido.delete()
        messages.success(request, f"El pedido de {producto_nombre} fue eliminado correctamente.")
        return redirect('clientes:lista_pedidos')

    # Si solo está entrando a ver la pantalla de confirmación (GET)
    return render(request, 'clientes/eliminar_pedido.html', {'pedido': pedido})


def unificar_proveedores(request):
    # Buscamos pedidos que tengan texto en el viejo campo pero que aún no tengan el oficial
    pedidos = Pedido.objects.exclude(proveedor__isnull=True).exclude(proveedor__exact='').filter(
        proveedor_oficial__isnull=True)
    vinculados = 0

    for pedido in pedidos:
        nombre_limpio = pedido.proveedor.strip().upper()

        # Buscamos el proveedor en la tabla nueva
        prov = Proveedor.objects.filter(nombre=nombre_limpio).first()

        if prov:
            pedido.proveedor_oficial = prov
            pedido.save()
            vinculados += 1

    return HttpResponse(f"¡Éxito! Se conectaron {vinculados} pedidos con su proveedor oficial en la nueva tabla.")


def registrar_bono_proveedor(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    proveedor = pedido.proveedor_oficial

    if not proveedor:
        messages.error(request, "Este pedido no tiene un proveedor oficial asignado.")
        return redirect('clientes:lista_pedidos')

    if request.method == 'POST':
        form = CancelarVentaForm(request.POST)

        # Apagamos validaciones automáticas
        if 'cuenta_proveedor' in form.fields: form.fields['cuenta_proveedor'].required = False
        if 'cuenta_cliente' in form.fields: form.fields['cuenta_cliente'].required = False

        if form.is_valid():
            with transaction.atomic():
                # --- 1. PROVEEDOR Y TESORERÍA: Cargamos el bono a su billetera y a cuentas ---
                monto_bono = pedido.precio_costo
                proveedor.saldo_a_favor += monto_bono
                proveedor.save()

                # Obtenemos el modelo Cuenta de forma segura a través de Movimiento (que ya está importado)
                Cuenta = Movimiento._meta.get_field('cuenta').related_model

                # Buscamos la cuenta puente (BONOS Y AJUSTES)
                cuenta_bonos = Cuenta.objects.filter(nombre__icontains="BONOS").first()

                if cuenta_bonos:
                    # Sumamos el saldo a la cuenta de Tesorería
                    cuenta_bonos.saldo_actual += monto_bono
                    cuenta_bonos.save()

                    # Dejamos la trazabilidad del ingreso del bono en Tesorería
                    Movimiento.objects.create(
                        cuenta=cuenta_bonos,
                        tipo='INGRESO',
                        monto=monto_bono,
                        concepto=f"Bono a favor - Proveedor: {proveedor.nombre} (Prod: {pedido.producto})",
                        referencia_pedido=str(pedido.id_pedido)
                    )

                # --- 2. CLIENTE: Resolvemos la situación ---
                tipo_reembolso = form.cleaned_data['tipo_reembolso_cliente']

                if tipo_reembolso == 'CONTADO':
                    cuenta_cli = form.cleaned_data['cuenta_cliente']
                    cuenta_cli.saldo_actual -= pedido.precio_venta
                    cuenta_cli.save()
                    # Movimiento ya está importado en la parte de arriba de tu archivo views.py
                    Movimiento.objects.create(
                        cuenta=cuenta_cli, tipo='EGRESO', monto=pedido.precio_venta,
                        concepto=f"Reembolso por bono proveedor - {pedido.producto}",
                        referencia_pedido=str(pedido.id_pedido)
                    )

                elif tipo_reembolso == 'CREDITO':
                    from django.apps import apps
                    Credito = apps.get_model('cartera', 'Credito')
                    Abono = apps.get_model('cartera', 'Abono')

                    credito_real = Credito.objects.filter(pedido=pedido, estado='ACTIVO').first()

                    if credito_real:
                        monto_deuda = credito_real.saldo_pendiente

                        # Si la cuenta no se encontró arriba, aplicamos un fallback de seguridad
                        if not cuenta_bonos:
                            cuenta_bonos = Cuenta.objects.first()

                        # A. Creamos el ABONO para que aparezca en el "Estado de Cuenta"
                        Abono.objects.create(
                            credito=credito_real,
                            monto=monto_deuda,
                            cuenta_destino=cuenta_bonos,
                            comprobante=f"DEV-{pedido.id_pedido}"[:20]
                        )

                        # B. Creamos el MOVIMIENTO para la trazabilidad de la deuda perdonada
                        Movimiento.objects.create(
                            cuenta=cuenta_bonos,
                            tipo='INGRESO',
                            monto=monto_deuda,
                            concepto=f"Cruce por devolución: {pedido.producto} (Cliente: {pedido.cliente.nombre})",
                            referencia_pedido=str(pedido.id_pedido)
                        )

                        # C. Seteamos la deuda en 0
                        credito_real.saldo_pendiente = 0
                        credito_real.estado = 'PAGADO'
                        credito_real.save()

                # --- 3. PEDIDO: Cerramos ---
                pedido.estado = 'CANCELADO'
                pedido.save()

            messages.success(request,
                             f"¡Éxito! Se generó el bono de ${int(monto_bono):,} y se cruzó la deuda del cliente.")
            return redirect('clientes:lista_pedidos')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Revisa el campo {field}: {error}")
    else:
        form = CancelarVentaForm()

    return render(request, 'clientes/confirmar_bono.html', {'pedido': pedido, 'form': form})


def lista_proveedores(request):
    # Traemos todos los proveedores, pero ponemos primero a los que tienen saldo a favor
    proveedores = Proveedor.objects.all().order_by('-saldo_a_favor', 'nombre')

    # Calculamos el total de bonos que tenemos en la calle para el resumen
    total_bonos = sum(p.saldo_a_favor for p in proveedores)

    return render(request, 'clientes/lista_proveedores.html', {
        'proveedores': proveedores,
        'total_bonos': total_bonos
    })


def crear_proveedor(request):
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            # Guardamos y limpiamos el nombre a mayúsculas automáticamente
            proveedor = form.save(commit=False)
            proveedor.nombre = proveedor.nombre.strip().upper()
            proveedor.save()
            messages.success(request, f"Proveedor {proveedor.nombre} creado exitosamente.")
            return redirect('clientes:lista_proveedores')
    else:
        form = ProveedorForm()

    return render(request, 'clientes/proveedor_form.html', {
        'form': form,
        'titulo': 'Nuevo Proveedor'
    })


def ejecutar_acciones_masivas(request):
    if request.method == 'POST':
        accion = request.POST.get('accion')
        pedidos_ids_str = request.POST.get('pedidos_ids', '')

        if not accion or not pedidos_ids_str:
            messages.error(request, "Error: Faltan datos para la acción masiva.")
            return redirect('clientes:lista_pedidos')

        # Convertimos el texto "1,2,3" en una lista y buscamos esos pedidos en la base de datos
        lista_ids = pedidos_ids_str.split(',')
        pedidos = Pedido.objects.filter(id_pedido__in=lista_ids)

        # ---------------------------------------------------------
        # ACCIÓN DIRECTA: Marcar como Recogidos
        # ---------------------------------------------------------
        if accion == 'marcar_recogidos':
            # Filtramos por seguridad para afectar solo a los que estén 'SEPARADO'
            pedidos_validos = pedidos.filter(estado='SEPARADO')
            cantidad = pedidos_validos.count()

            # El comando .update() guarda todos los cambios en 1 segundo sin usar ciclos for
            pedidos_validos.update(estado='RECOGIDO')

            messages.success(request, f"¡Éxito! {cantidad} pedidos fueron pasados al estado RECOGIDO.")
            return redirect('clientes:lista_pedidos')

        # ---------------------------------------------------------
        # ACCIÓN CON PASO INTERMEDIO: Asignar Proveedor
        # ---------------------------------------------------------
        elif accion == 'asignar_proveedor':
            # Usamos nuestro truco maestro para encontrar el modelo Proveedor
            Proveedor = Pedido._meta.get_field('proveedor_oficial').related_model

            # Verificamos si ya eligieron al proveedor en la pantalla intermedia
            nuevo_proveedor_id = request.POST.get('nuevo_proveedor_id')

            if nuevo_proveedor_id:
                # Si ya lo eligieron, hacemos la actualización masiva
                proveedor_seleccionado = Proveedor.objects.get(id=nuevo_proveedor_id)
                pedidos.update(proveedor_oficial=proveedor_seleccionado)

                messages.success(request,
                                 f"¡Éxito! Se asignó {proveedor_seleccionado.nombre} a {pedidos.count()} pedidos.")
                return redirect('clientes:lista_pedidos')
            else:
                # Si no lo han elegido, los mandamos a la pantalla para que lo elijan
                proveedores = Proveedor.objects.all().order_by('nombre')
                return render(request, 'clientes/asignar_proveedor_masivo.html', {
                    'pedidos_ids': pedidos_ids_str,
                    'pedidos': pedidos,
                    'proveedores': proveedores,
                    'accion': accion
                })

        elif accion == 'pagar_masivo':
            messages.info(request, "El módulo de pago masivo será nuestro próximo reto.")
            return redirect('clientes:lista_pedidos')

        else:
            messages.error(request, "Acción no reconocida.")
            return redirect('clientes:lista_pedidos')

    return redirect('clientes:lista_pedidos')