from django import forms
from .models import Producto, MovimientoStock, AreaServicio, CATEGORIA_CHOICES, UNIDAD_CHOICES


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['codigo_barras', 'nombre', 'descripcion', 'categoria', 'unidad_medida', 'stock_minimo', 'imagen_url']
        widgets = {
            'codigo_barras': forms.TextInput(attrs={
                'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
                'placeholder': 'Ej: 7790001234567',
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
                'placeholder': 'Nombre del producto',
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
                'rows': 3,
                'placeholder': 'Descripción opcional',
            }),
            'categoria': forms.Select(attrs={
                'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
            }),
            'unidad_medida': forms.Select(attrs={
                'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
            }),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
                'min': 0,
            }),
            'imagen_url': forms.URLInput(attrs={
                'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
                'placeholder': 'https://...',
            }),
        }


class MovimientoManualForm(forms.Form):
    TIPO_CHOICES = [
        ('entrada', 'Entrada (+)'),
        ('salida', 'Salida (-)'),
    ]

    tipo = forms.ChoiceField(
        choices=TIPO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
        }),
    )
    cantidad = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
            'min': 1,
        }),
    )
    fecha_vencimiento = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
            'type': 'date',
        }),
    )
    numero_lote = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
            'placeholder': 'Nro. de lote (opcional)',
        }),
    )
    observacion = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
            'placeholder': 'Observación (opcional)',
        }),
    )


class FiltroHistorialForm(forms.Form):
    area = forms.ModelChoiceField(
        queryset=AreaServicio.objects.filter(activa=True),
        required=False,
        empty_label='Todas las áreas',
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
        }),
    )
    tipo = forms.ChoiceField(
        choices=[('', 'Entradas y Salidas'), ('entrada', 'Solo Entradas'), ('salida', 'Solo Salidas')],
        required=False,
        widget=forms.Select(attrs={
            'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
        }),
    )
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
            'type': 'date',
        }),
    )
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
            'type': 'date',
        }),
    )
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500',
            'placeholder': 'Buscar producto...',
        }),
    )
