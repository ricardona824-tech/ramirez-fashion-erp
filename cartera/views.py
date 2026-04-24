from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from .models import Credito, Abono
from .forms import CreditoForm, AbonoForm
from tesoreria.models import Movimiento


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
