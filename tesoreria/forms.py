from django import forms
from .models import Cuenta

class CuentaForm(forms.ModelForm):
    class Meta:
        model = Cuenta
        fields = ['nombre', 'tipo', 'saldo_actual']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. Efectivo Principal'}),
            'tipo': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'saldo_actual': forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'step': '0.01'}),
        }

CATEGORIAS_GASTO = [
    ('Logística', 'Logística'),
    ('Marketing', 'Marketing'),
    ('Otros', 'Otros'),
]

class GastoForm(forms.Form):
    """Formulario para registrar gastos operativos (HU 06)"""
    cuenta_origen = forms.ModelChoiceField(
        queryset=Cuenta.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label="Cuenta de Origen"
    )
    monto = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        localize=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Ej. 150.000',
            'inputmode': 'numeric'
        }),
        label="Monto del Gasto"
    )
    categoria = forms.ChoiceField(
        choices=CATEGORIAS_GASTO,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label="Categoría"
    )
    descripcion = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. Pago de publicidad'}),
        label="Descripción adicional"
    )

class TransferenciaForm(forms.Form):
    """Formulario para mover dinero entre cuentas (HU 06)"""
    cuenta_origen = forms.ModelChoiceField(
        queryset=Cuenta.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label="Cuenta de Origen (-)"
    )
    cuenta_destino = forms.ModelChoiceField(
        queryset=Cuenta.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label="Cuenta de Destino (+)"
    )
    monto = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        localize=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Ej. 150.000',
            'inputmode': 'numeric'
        }),
        label="Monto a Transferir"
    )
    concepto = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. Traslado para pago de proveedores'}),
        label="Concepto"
    )