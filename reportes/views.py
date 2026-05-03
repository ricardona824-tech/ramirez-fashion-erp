from django.shortcuts import render
from django.db.models import Sum
from clientes.models import Pedido, Cliente
from tesoreria.models import Cuenta, Gasto
from cartera.models import Credito, Abono
from django.utils.dateparse import parse_date


def dashboard_gerencial(request):
    """Vista principal de reportes y estadísticas para gerencia con filtro de fechas."""

    # 1. Capturar las fechas del filtro que envía el usuario
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    # 2. Consultas base
    pedidos = Pedido.objects.filter(estado='ENTREGADO')
    gastos = Gasto.objects.all()

    # 3. Aplicar los filtros de fecha si el usuario los seleccionó
    if fecha_inicio:
        # Para los pedidos usamos "fecha_registro", para los gastos usamos "fecha"
        pedidos = pedidos.filter(fecha_registro__date__gte=fecha_inicio)
        gastos = gastos.filter(fecha__date__gte=fecha_inicio)
    if fecha_fin:
        pedidos = pedidos.filter(fecha_registro__date__lte=fecha_fin)
        gastos = gastos.filter(fecha__date__lte=fecha_fin)

    # 4. Cálculos del Estado de Resultados (Filtrables por fecha)
    total_ventas = pedidos.aggregate(total=Sum('precio_venta'))['total'] or 0
    total_costos = pedidos.aggregate(total=Sum('precio_costo'))['total'] or 0
    utilidad_bruta = total_ventas - total_costos

    total_gastos = gastos.aggregate(total=Sum('monto'))['total'] or 0
    utilidad_neta = utilidad_bruta - total_gastos

    # 5. Cálculos del Balance / Tesorería (Saldos Actuales, NO se filtran por fecha)
    cartera_activa = Credito.objects.filter(estado='ACTIVO')
    total_cartera = cartera_activa.aggregate(total=Sum('saldo_pendiente'))['total'] or 0
    total_tesoreria = Cuenta.objects.aggregate(total=Sum('saldo_actual'))['total'] or 0
    capital_total_negocio = total_tesoreria + total_cartera

    context = {
        'total_ventas': total_ventas,
        'total_costos': total_costos,
        'utilidad_bruta': utilidad_bruta,
        'total_gastos': total_gastos,
        'utilidad_neta': utilidad_neta,
        'total_cartera': total_cartera,
        'total_tesoreria': total_tesoreria,
        'capital_total_negocio': capital_total_negocio,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    }

    return render(request, 'reportes/dashboard_gerencial.html', context)


def estado_cuenta_cliente(request):
    """Genera un extracto detallado de movimientos de cartera por cliente."""
    clientes = Cliente.objects.all().order_by('nombre')

    cliente_id = request.GET.get('cliente_id')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    movimientos_filtrados = []
    saldo_actual = 0
    cliente_seleccionado = None

    if cliente_id:
        cliente_seleccionado = Cliente.objects.get(id=cliente_id)

        # 1. Traer toda la historia: Créditos (Deudas) y Abonos (Pagos)
        creditos = Credito.objects.filter(cliente_id=cliente_id)
        abonos = Abono.objects.filter(credito__cliente_id=cliente_id)

        historial = []
        for c in creditos:
            # Verificamos si el crédito viene de un pedido de ropa específico
            if c.pedido and c.pedido.producto:
                texto_detalle = f"Compra: {c.pedido.producto}"
            else:
                texto_detalle = f"Nueva deuda (Crédito #{c.id})"

            historial.append({
                'fecha': c.fecha_registro,
                'detalle': texto_detalle,
                'cargo': c.monto_total,
                'abono': 0,
                'es_cargo': True
            })

        for a in abonos:
            historial.append({
                'fecha': a.fecha,
                'detalle': f"Abono recibido",
                'cargo': 0,
                'abono': a.monto,
                'es_cargo': False
            })

        # 2. Ordenar todo de más antiguo a más nuevo
        historial.sort(key=lambda x: x['fecha'])

        # 3. Calcular el saldo renglón por renglón
        saldo_acumulado = 0
        for item in historial:
            if item['es_cargo']:
                saldo_acumulado += item['cargo']
            else:
                saldo_acumulado -= item['abono']
            item['saldo_final'] = saldo_acumulado

        # 4. Filtrar visualmente por las fechas seleccionadas
        for item in historial:
            incluir = True
            fecha_item = item['fecha'].date()

            if fecha_inicio and fecha_item < parse_date(fecha_inicio):
                incluir = False
            if fecha_fin and fecha_item > parse_date(fecha_fin):
                incluir = False

            if incluir:
                movimientos_filtrados.append(item)

        saldo_actual = saldo_acumulado

    context = {
        'clientes': clientes,
        'cliente_seleccionado': cliente_seleccionado,
        'movimientos': movimientos_filtrados,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'saldo_actual': saldo_actual
    }
    return render(request, 'reportes/estado_cuenta.html', context)


def resumen_cartera(request):
    # 1. Traemos la lista de todos los clientes
    clientes = Cliente.objects.all()

    lista_cartera = []
    total_general_cartera = 0

    for c in clientes:
        # 2. Sumamos directamente el "saldo_pendiente" de todos los créditos de este cliente
        saldo = Credito.objects.filter(cliente=c).aggregate(total=Sum('saldo_pendiente'))['total'] or 0

        # 3. Solo incluimos a los que deben dinero (saldo > 0)
        if saldo > 0:
            lista_cartera.append({
                'id': c.id,
                'nombre': c.nombre,
                'telefono': c.whatsapp,
                'saldo': saldo
            })
            total_general_cartera += saldo

    # 4. Ordenamos para que los que más deben salgan arriba
    lista_cartera = sorted(lista_cartera, key=lambda x: x['saldo'], reverse=True)

    return render(request, 'reportes/resumen_cartera.html', {
        'clientes': lista_cartera,
        'total_general': total_general_cartera
    })