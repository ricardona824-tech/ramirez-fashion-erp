from django import forms
from .models import Cliente, Pedido
from tesoreria.models import Cuenta


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'whatsapp', 'direccion', 'ciudad']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. Juan Pérez'}),
            'whatsapp': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. 3001234567'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. Calle 123 # 45-67'}),
            'ciudad': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. Medellín'}),
        }

class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        # Campos exactos según la HU 02
        fields = ['cliente', 'producto', 'talla', 'color', 'proveedor', 'precio_costo', 'precio_venta']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'producto': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. Camisa Oversize'}),
            'talla': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. M'}),
            'color': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. Negro'}),
            'proveedor': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. Proveedor Textil SAS'}),
            'precio_costo': forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. 35000'}),
            'precio_venta': forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. 70000'}),
        }

from tesoreria.models import Cuenta

class PagarProveedorForm(forms.Form):
    """Formulario para elegir la cuenta al pagar un pedido (HU 05)."""
    cuenta_origen = forms.ModelChoiceField(
        queryset=Cuenta.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label="Cuenta origen del pago"
    )

class CobrarClienteForm(forms.Form):
    """Formulario para elegir cómo paga el cliente al entregar (HU 08)."""
    TIPOS_PAGO = [
        ('CONTADO', 'De Contado (Pago inmediato)'),
        ('CREDITO', 'A Crédito (Fiado)')
    ]
    tipo_pago = forms.ChoiceField(
        choices=TIPOS_PAGO,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg mb-3', 'id': 'id_tipo_pago'}),
        label="Método de Pago"
    )
    cuenta_destino = forms.ModelChoiceField(
        queryset=Cuenta.objects.all(),
        required=False, # ¡Importante! Si es a crédito no necesitamos cuenta
        widget=forms.Select(attrs={'class': 'form-select form-select-lg', 'id': 'id_cuenta_destino'}),
        label="¿A qué cuenta ingresa el dinero? (Solo para pago de contado)"
    )

    def clean(self):
        cleaned_data = super().clean()
        tipo_pago = cleaned_data.get('tipo_pago')
        cuenta_destino = cleaned_data.get('cuenta_destino')

        # Validación: Si es de contado, obligamos a que elija una cuenta
        if tipo_pago == 'CONTADO' and not cuenta_destino:
            self.add_error('cuenta_destino', 'Debe seleccionar una cuenta si el pago es de contado.')
        return cleaned_data


class CancelarVentaForm(forms.Form):
    """Formulario para gestionar reembolsos logísticos y contables (Camino B)."""
    cuenta_proveedor = forms.ModelChoiceField(
        queryset=Cuenta.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg mb-3'}),
        label="1. ¿A qué cuenta te devuelve el dinero el PROVEEDOR? (+ Ingreso)"
    )

    TIPOS_REEMBOLSO = [
        ('CONTADO', 'Devolver dinero al cliente (Efectivo/Transferencia)'),
        ('CREDITO', 'Anular deuda pendiente en Cartera')
    ]
    tipo_reembolso_cliente = forms.ChoiceField(
        choices=TIPOS_REEMBOLSO,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg mb-3', 'id': 'id_tipo_reembolso'}),
        label="2. ¿Cómo le devuelves al CLIENTE? (- Egreso o Cartera)"
    )

    cuenta_cliente = forms.ModelChoiceField(
        queryset=Cuenta.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg', 'id': 'id_cuenta_cliente'}),
        label="¿De qué cuenta sale el reembolso para el cliente?"
    )

    def clean(self):
        cleaned_data = super().clean()
        tipo_reembolso = cleaned_data.get('tipo_reembolso_cliente')
        cuenta_cliente = cleaned_data.get('cuenta_cliente')

        if tipo_reembolso == 'CONTADO' and not cuenta_cliente:
            self.add_error('cuenta_cliente', 'Debe seleccionar una cuenta para sacar el dinero del reembolso.')
        return cleaned_data