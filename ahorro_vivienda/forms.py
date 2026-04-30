from django import forms
from django.forms import inlineformset_factory
from .models import ConfiguracionMeta, Cotizacion, Snapshot, CapitalItem, Conversion


class ConfiguracionMetaForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionMeta
        fields = ['nombre', 'meta_usd', 'fecha_objetivo', 'notas']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'Ej: Anticipo primera vivienda',
            }),
            'meta_usd': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': '30000',
                'step': '100',
                'min': '0',
            }),
            'fecha_objetivo': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'type': 'date',
            }),
            'notas': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'rows': 3,
                'placeholder': 'Condiciones del crédito, banco, etc.',
            }),
        }
        labels = {
            'nombre': 'Nombre del proyecto',
            'meta_usd': 'Meta en USD (u$s)',
            'fecha_objetivo': 'Fecha objetivo (opcional)',
            'notas': 'Notas',
        }


class CotizacionForm(forms.ModelForm):
    class Meta:
        model = Cotizacion
        fields = ['fecha', 'blue_compra', 'blue_venta', 'oficial_compra', 'oficial_venta', 'mep', 'eur_usd', 'fuente']
        widgets = {
            'fecha': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
                'type': 'date',
            }),
            'blue_compra': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
                'step': '0.01', 'min': '0',
            }),
            'blue_venta': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
                'step': '0.01', 'min': '0',
            }),
            'oficial_compra': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
                'step': '0.01', 'min': '0',
            }),
            'oficial_venta': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
                'step': '0.01', 'min': '0',
            }),
            'mep': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
                'step': '0.01', 'min': '0',
            }),
            'eur_usd': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
                'step': '0.0001', 'min': '0',
            }),
            'fuente': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
            }),
        }


class SnapshotForm(forms.ModelForm):
    class Meta:
        model = Snapshot
        fields = ['fecha', 'notas']
        widgets = {
            'fecha': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'type': 'date',
            }),
            'notas': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'rows': 2,
                'placeholder': 'Observaciones opcionales...',
            }),
        }


class CapitalItemForm(forms.ModelForm):
    class Meta:
        model = CapitalItem
        fields = ['nombre', 'tipo', 'moneda', 'monto_original', 'cotizacion_tipo', 'cotizacion_manual', 'orden']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
                'placeholder': 'Ej: Efectivo USD, Cuenta Galicia',
            }),
            'tipo': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
            }),
            'moneda': forms.Select(attrs={
                'class': 'moneda-select w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
            }),
            'monto_original': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
                'step': '0.01', 'min': '0',
                'placeholder': '0.00',
            }),
            'cotizacion_tipo': forms.Select(attrs={
                'class': 'cotizacion-tipo-select w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
            }),
            'cotizacion_manual': forms.NumberInput(attrs={
                'class': 'cotizacion-manual-input w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm',
                'step': '0.01', 'min': '0',
                'placeholder': 'Solo si elegís manual',
            }),
            'orden': forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        monto = cleaned_data.get('monto_original')
        if monto is not None and monto <= 0:
            self.add_error('monto_original', 'El monto debe ser mayor a 0.')
        cotiz_tipo = cleaned_data.get('cotizacion_tipo')
        cotiz_manual = cleaned_data.get('cotizacion_manual')
        if cotiz_tipo == 'manual' and (cotiz_manual is None or cotiz_manual <= 0):
            self.add_error('cotizacion_manual', 'Debés ingresar la cotización manual.')
        return cleaned_data


CapitalItemFormSet = inlineformset_factory(
    Snapshot,
    CapitalItem,
    form=CapitalItemForm,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class ConversionForm(forms.ModelForm):
    class Meta:
        model = Conversion
        fields = ['fecha', 'descripcion', 'moneda_origen', 'monto_origen',
                  'moneda_destino', 'monto_destino', 'cotizacion_efectiva', 'notas']
        widgets = {
            'fecha': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'type': 'date',
            }),
            'descripcion': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'Ej: Compra USD en cueva, Transferencia USDT',
            }),
            'moneda_origen': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            }),
            'monto_origen': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'step': '0.01', 'min': '0', 'placeholder': '0.00',
            }),
            'moneda_destino': forms.Select(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            }),
            'monto_destino': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'step': '0.01', 'min': '0', 'placeholder': '0.00',
            }),
            'cotizacion_efectiva': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'step': '0.01', 'min': '0',
                'placeholder': 'Tipo de cambio real (ej: 1350)',
            }),
            'notas': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'rows': 2,
                'placeholder': 'Proveedor, referencia, etc.',
            }),
        }
        labels = {
            'cotizacion_efectiva': 'Cotización efectiva usada',
        }
