from django.shortcuts import render, redirect
from django.db.models import Sum
from django.db import transaction
from django.contrib import messages
from .models import Cuenta, Movimiento, Gasto
from .forms import CuentaForm, GastoForm, TransferenciaForm


def dashboard_tesoreria(request):
    """
    Vista principal de Tesorería (HU 04).
    Muestra las cuentas y el saldo total consolidado.
    """
    cuentas = Cuenta.objects.all()
    # Calcular saldo total consolidado sumando la columna saldo_actual
    saldo_total = cuentas.aggregate(total=Sum('saldo_actual'))['total'] or 0.00

    # Lógica para procesar la creación de una nueva cuenta
    if request.method == 'POST':
        form = CuentaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('tesoreria:dashboard')
    else:
        form = CuentaForm()

    context = {
        'cuentas': cuentas,
        'saldo_total': saldo_total,
        'form': form,
    }
    return render(request, 'tesoreria/dashboard.html', context)


def registrar_gasto(request):
    """Vista para procesar un gasto operativo"""
    if request.method == 'POST':
        form = GastoForm(request.POST)
        if form.is_valid():
            cuenta = form.cleaned_data['cuenta_origen']
            monto = form.cleaned_data['monto']

            if cuenta.saldo_actual < monto:
                messages.error(request, f"¡Error! Saldo insuficiente en la cuenta: {cuenta.nombre}.")
            else:
                with transaction.atomic():
                    # 1. Restar el dinero del banco
                    cuenta.saldo_actual -= monto
                    cuenta.save()

                    # 2. CREAR EL REGISTRO EN EL NUEVO MODELO DE GASTOS (Para Reportes)
                    Gasto.objects.create(
                        cuenta=cuenta,
                        monto=monto,
                        categoria=form.cleaned_data['categoria'],
                        descripcion=form.cleaned_data['descripcion']
                    )

                    # 3. Registrar el log de egreso (Para Auditoría de Tesorería)
                    concepto_gasto = f"Gasto {form.cleaned_data['categoria']}: {form.cleaned_data['descripcion']}"
                    Movimiento.objects.create(cuenta=cuenta, tipo='EGRESO', monto=monto, concepto=concepto_gasto)

                messages.success(request, "Gasto registrado correctamente.")
                return redirect('tesoreria:dashboard')
    else:
        form = GastoForm()

    return render(request, 'tesoreria/transaccion_form.html', {'form': form, 'titulo': 'Registrar Gasto Operativo'})


def registrar_transferencia(request):
    """Vista para transferir dinero de una cuenta a otra"""
    if request.method == 'POST':
        form = TransferenciaForm(request.POST)
        if form.is_valid():
            origen = form.cleaned_data['cuenta_origen']
            destino = form.cleaned_data['cuenta_destino']
            monto = form.cleaned_data['monto']

            # Validaciones clave
            if origen == destino:
                messages.error(request, "La cuenta de origen y destino no pueden ser la misma.")
            elif origen.saldo_actual < monto:
                messages.error(request, f"¡Error! Saldo insuficiente en {origen.nombre}.")
            else:
                with transaction.atomic():
                    # 1. Mover el dinero
                    origen.saldo_actual -= monto
                    origen.save()
                    destino.saldo_actual += monto
                    destino.save()

                    # 2. Registrar los logs (Egreso en origen, Ingreso en destino)
                    concepto_log = form.cleaned_data['concepto']
                    Movimiento.objects.create(cuenta=origen, tipo='EGRESO', monto=monto,
                                              concepto=f"Transferencia enviada a {destino.nombre} - {concepto_log}")
                    Movimiento.objects.create(cuenta=destino, tipo='INGRESO', monto=monto,
                                              concepto=f"Transferencia recibida de {origen.nombre} - {concepto_log}")

                messages.success(request, "Transferencia realizada con éxito.")
                return redirect('tesoreria:dashboard')
    else:
        form = TransferenciaForm()

    return render(request, 'tesoreria/transaccion_form.html', {'form': form, 'titulo': 'Transferencia de Dinero'})
