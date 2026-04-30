import os
import csv
import django
from datetime import datetime
from decimal import Decimal

# 1. CONECTAR EL SCRIPT A TU ERP (⚠️ CAMBIA 'ramirez_erp.settings' POR TU RUTA REAL)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# Importar tus modelos (Asegúrate de que los nombres de las apps sean los correctos)
from clientes.models import Cliente, Pedido
from cartera.models import Credito, Abono
from tesoreria.models import Cuenta


def limpiar_monto(valor):
    texto = str(valor).strip().replace('$', '').replace(' ', '').replace('.', '').replace(',', '.')
    if texto in ['', '-']: return Decimal('0.00')
    try:
        return Decimal(texto)
    except:
        return Decimal('0.00')


def ejecutar_importacion():
    print("Iniciando la migración histórica...")

    # 2. CREAR LA CUENTA BANCARIA COMODÍN
    cuenta_migracion, _ = Cuenta.objects.get_or_create(
        nombre='Caja Migración Excel',
        defaults={'tipo': 'EFECTIVO', 'saldo_actual': 0}
    )

    archivo = 'datos_limpios.csv'

    with open(archivo, 'r', encoding='latin-1') as f:
        primera_linea = f.readline()
        delimitador = ';' if ';' in primera_linea else ','
        f.seek(0)
        reader = csv.DictReader(f, delimiter=delimitador)

        for i, fila in enumerate(reader):
            nombre_cliente = fila['NOMBRE'].strip()
            fecha_str = fila['FECHA'].strip()
            concepto = fila['CONCEPTO'].strip()

            # Limpiamos usando los nombres de encabezados de tu Excel
            venta_valor = limpiar_monto(fila['VALOR UNITARIO'])
            abono_valor = limpiar_monto(fila['ABONO'])

            if not nombre_cliente:
                continue

            # Convertir fecha de texto a Fecha Real
            try:
                fecha_dt = datetime.strptime(fecha_str, '%Y-%m-%d')
            except ValueError:
                fecha_dt = datetime.now()  # Por si hay una fecha dañada extrema

            # 3. CREAR O BUSCAR AL CLIENTE (Con WhatsApp Dummy)
            cliente, created = Cliente.objects.get_or_create(
                nombre=nombre_cliente,
                defaults={
                    'whatsapp': f"MIGRACION_{i}",  # Para saltar la regla del unique=True
                    'direccion': 'Pendiente',
                    'ciudad': 'Pendiente'
                }
            )

            # 4. REGISTRAR VENTA -> CREA PEDIDO Y CRÉDITO
            if venta_valor > 0:
                # Se crea el pedido
                pedido = Pedido.objects.create(
                    cliente=cliente,
                    producto=concepto,
                    precio_costo=0,
                    precio_venta=venta_valor,
                    talla='N/A', color='N/A', proveedor='Migración',
                    estado='ENTREGADO'
                )
                # Viaje en el tiempo para el Pedido
                Pedido.objects.filter(pk=pedido.pk).update(fecha_registro=fecha_dt, fecha_actualizacion=fecha_dt)

                # Se crea el crédito amarrado al pedido
                credito = Credito.objects.create(
                    cliente=cliente,
                    pedido=pedido,
                    monto_total=venta_valor,
                    saldo_pendiente=venta_valor,
                    estado='ACTIVO'
                )
                # Viaje en el tiempo para el Crédito
                Credito.objects.filter(pk=credito.pk).update(fecha_registro=fecha_dt)

            # 5. REGISTRAR ABONO -> BUSCA CRÉDITOS ACTIVOS (ALGORITMO FIFO)
            if abono_valor > 0:
                abono_restante = abono_valor

                # Traer deudas activas desde la más vieja a la más nueva
                deudas_activas = Credito.objects.filter(cliente=cliente, estado='ACTIVO').order_by('fecha_registro',
                                                                                                   'id')

                for deuda in deudas_activas:
                    if abono_restante <= 0:
                        break  # Ya se repartió todo el dinero

                    # ¿Cuánto le podemos meter a esta deuda? Lo que alcance.
                    pago_a_esta_deuda = min(abono_restante, deuda.saldo_pendiente)

                    # Se crea el Abono físico
                    abono_obj = Abono.objects.create(
                        credito=deuda,
                        monto=pago_a_esta_deuda,
                        cuenta_destino=cuenta_migracion,
                        comprobante='Migración Excel'
                    )
                    # Viaje en el tiempo para el Abono
                    Abono.objects.filter(pk=abono_obj.pk).update(fecha=fecha_dt)

                    # Se actualiza el crédito (se le resta la plata)
                    deuda.saldo_pendiente -= pago_a_esta_deuda
                    if deuda.saldo_pendiente <= 0:
                        deuda.estado = 'PAGADO'
                    deuda.save()

                    # Se descuenta la plata de la mano del robot
                    abono_restante -= pago_a_esta_deuda

                # Si sobró plata del abono (el cliente pagó por adelantado o pagó de más)
                # Creamos un crédito a favor (Saldo negativo) para no perder el dinero
                if abono_restante > 0:
                    cred_extra = Credito.objects.create(
                        cliente=cliente,
                        monto_total=0,
                        saldo_pendiente=-abono_restante,
                        estado='PAGADO'  # No debe plata
                    )
                    Credito.objects.filter(pk=cred_extra.pk).update(fecha_registro=fecha_dt)

                    ab_extra = Abono.objects.create(
                        credito=cred_extra,
                        monto=abono_restante,
                        cuenta_destino=cuenta_migracion,
                        comprobante='Abono extra (Saldo a favor)'
                    )
                    Abono.objects.filter(pk=ab_extra.pk).update(fecha=fecha_dt)

                # Sumar el dinero físico a la Cuenta de Tesorería
                cuenta_migracion.saldo_actual += abono_valor
                cuenta_migracion.save()

    print(f"\n🎉 ¡MIGRACIÓN COMPLETADA! 🎉")
    print(
        f"La cuenta '{cuenta_migracion.nombre}' quedó con un saldo histórico de: ${cuenta_migracion.saldo_actual:,.2f}")


if __name__ == '__main__':
    ejecutar_importacion()