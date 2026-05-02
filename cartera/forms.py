from django import forms
from .models import Credito, Abono
from tesoreria.models import Cuenta

class CreditoForm(forms.ModelForm):
    class Meta:
        model = Credito
        fields = ['cliente', 'pedido', 'monto_total']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'pedido': forms.Select(attrs={'class': 'form-select form-select-lg'}),
        }
    monto_total = forms.DecimalField(
        max_digits=15, decimal_places=2, localize=True,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'inputmode': 'numeric', 'placeholder': 'Ej. 150.000'}),
        label="Monto Total a Fiar"
    )

class AbonoForm(forms.ModelForm):
    class Meta:
        model = Abono
        fields = ['monto', 'cuenta_destino', 'comprobante']
        widgets = {
            'cuenta_destino': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'comprobante': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ej. Transferencia a Bancolombia'}),
        }
    monto = forms.DecimalField(
        max_digits=15, decimal_places=2, localize=True,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'inputmode': 'numeric', 'placeholder': 'Ej. 50.000'}),
        label="Valor del Abono"
    )

class AbonoGlobalForm(forms.Form):
    monto = forms.DecimalField(max_digits=15, decimal_places=2, label="Monto a Abonar")
    cuenta_destino = forms.ModelChoiceField(queryset=Cuenta.objects.all(), label="Cuenta destino")
    comprobante = forms.CharField(max_length=100, required=False, label="N° Comprobante / Referencia")