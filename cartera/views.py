from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.urls import reverse
from .models import Credito, Abono
from .forms import CreditoForm, AbonoForm, AbonoGlobalForm
from tesoreria.models import Movimiento, Cuenta
from decimal import Decimal
from clientes.models import Cliente



def lista_creditos(request):
    """Muestra la lista de deudores."""
    creditos = Credito.objects.all()
    return render(request, 'cartera/lista_creditos.html', {'creditos': creditos})


def crear_credito(request):
    """Registra un nuevo fiado a un cliente."""
    if request.method == 'POST':
        form = CreditoForm(request.POST)
        if form.is_valid():
            credito = form.save(commit=False)
            credito.saldo_pendiente = credito.monto_total  # Al inicio deben todo
            credito.save()
            messages.success(request, "Crédito registrado con éxito.")
            return redirect('cartera:lista_creditos')
    else:
        form = CreditoForm()
    return render(request, 'cartera/cartera_form.html', {'form': form, 'titulo': 'Registrar Nuevo Fiado'})


def registrar_abono(request, pk):
    """Registra un pago, actualiza saldos e ingresa el dinero a tesorería."""
    credito = get_object_or_404(Credito, pk=pk)

    if request.method == 'POST':
        form = AbonoForm(request.POST)
        if form.is_valid():
            abono = form.save(commit=False)
            abono.credito = credito

            # Validación: No permitir que paguen más de lo que deben
            if abono.monto > credito.saldo_pendiente:
                messages.error(request, "El abono no puede ser mayor al saldo pendiente.")
            else:
                with transaction.atomic():
                    # 1. Guardar el abono
                    abono.save()

                    # 2. Descontar la deuda del cliente
                    credito.saldo_pendiente -= abono.monto
                    if credito.saldo_pendiente == 0:
                        credito.estado = 'PAGADO'
                    credito.save()

                    # 3. Sumar el dinero a la cuenta de tesorería
                    cuenta = abono.cuenta_destino
                    cuenta.saldo_actual += abono.monto
                    cuenta.save()

                    # 4. Registrar en el log contable
                    Movimiento.objects.create(
                        cuenta=cuenta, tipo='INGRESO', monto=abono.monto,
                        concepto=f"Abono de {credito.cliente.nombre} (Comprobante: {abono.comprobante})"
                    )

                messages.success(request, f"¡Abono de ${int(abono.monto):,} registrado exitosamente!")
                return redirect('cartera:lista_creditos')
    else:
        form = AbonoForm()

    return render(request, 'cartera/cartera_form.html',
                  {'form': form, 'titulo': f'Registrar Abono - {credito.cliente.nombre}', 'credito': credito})


def registrar_abono_global(request, cliente_id):
    """Registra un pago global y lo distribuye en las deudas activas (FIFO)."""
    cliente = get_object_or_404(Cliente, pk=cliente_id)

    # Sumar la deuda total para validaciones
    deudas_activas = Credito.objects.filter(cliente=cliente, estado='ACTIVO').order_by('fecha_registro', 'id')
    deuda_total = sum(d.saldo_pendiente for d in deudas_activas)

    if request.method == 'POST':
        form = AbonoGlobalForm(request.POST)
        if form.is_valid():
            monto_abono = form.cleaned_data['monto']
            cuenta = form.cleaned_data['cuenta_destino']
            comprobante = form.cleaned_data['comprobante']

            if monto_abono <= 0:
                messages.error(request, "El abono debe ser mayor a cero.")
            else:
                with transaction.atomic():
                    monto_restante = monto_abono

                    # 1. Distribuir la plata en las deudas viejas primero
                    for deuda in deudas_activas:
                        if monto_restante <= 0:
                            break

                        pago_a_esta_deuda = min(monto_restante, deuda.saldo_pendiente)

                        # Crear el registro del abono
                        Abono.objects.create(
                            credito=deuda,
                            monto=pago_a_esta_deuda,
                            cuenta_destino=cuenta,
                            comprobante=comprobante
                        )

                        # Restar a la deuda
                        deuda.saldo_pendiente -= pago_a_esta_deuda
                        if deuda.saldo_pendiente == 0:
                            deuda.estado = 'PAGADO'
                        deuda.save()

                        # Descontar la plata que el robot tiene en la mano
                        monto_restante -= pago_a_esta_deuda

                    # 2. Si pagó de más (Saldo a favor)
                    if monto_restante > 0:
                        cred_extra = Credito.objects.create(
                            cliente=cliente, monto_total=0,
                            saldo_pendiente=-monto_restante, estado='PAGADO'
                        )
                        Abono.objects.create(
                            credito=cred_extra, monto=monto_restante,
                            cuenta_destino=cuenta, comprobante=f"{comprobante} (Saldo a favor)"
                        )

                    # 3. Sumar el dinero a tesorería
                    cuenta.saldo_actual += monto_abono
                    cuenta.save()

                    # 4. Registrar en el libro contable mayor (Movimiento)
                    Movimiento.objects.create(
                        cuenta=cuenta, tipo='INGRESO', monto=monto_abono,
                        concepto=f"Abono Global de {cliente.nombre} (Comp: {comprobante})"
                    )

                messages.success(request, f"¡Abono global de ${int(monto_abono):,} distribuido correctamente!")

                # 🔴 EL GPS CORREGIDO PARA VOLVER AL REPORTE
                url_destino = reverse('reportes:estado_cuenta_cliente')
                return redirect(f"{url_destino}?cliente_id={cliente.id}")
    else:
        # Si la deuda es cero, le mostramos un aviso en el formulario
        if deuda_total <= 0:
            messages.warning(request, f"{cliente.nombre} actualmente no tiene deudas pendientes.")
        form = AbonoGlobalForm()

    return render(request, 'cartera/cartera_form.html', {
        'form': form,
        'titulo': f'Registrar Abono a {cliente.nombre}',
        'deuda_total': deuda_total
    })
