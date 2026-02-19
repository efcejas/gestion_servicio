"""
Comando Django para importar estudios desde Excel del EGES

Uso:
    Local:
        python manage.py importar_estudios_eges archivo.xlsx --tipo TOM
    
    Heroku:
        heroku run python manage.py importar_estudios_eges estudios.xlsx --tipo TOM --app tu-app

Características:
    - Parseo inteligente de variantes (con contraste, angio, difusión, etc.)
    - Asignación automática de precios según reglas de negocio
    - Actualización de estudios existentes
    - Modo dry-run para previsualización
    - Reporte detallado de operaciones
"""

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal
from liquidacion.models import Estudios
import re


class Command(BaseCommand):
    help = 'Importa estudios desde Excel del EGES con parseo inteligente de variantes'
    
    # ========== REGLAS DE NEGOCIO: PRECIOS BASE ==========
    PRECIOS_BASE = {
        'TOM': {
            'base': Decimal('4000.00'),
            'con_contraste': Decimal('5000.00'),
            'angio': Decimal('7000.00'),
            'precio_unico': True,
        },
        'RES': {
            'base': Decimal('5000.00'),
            'con_contraste': Decimal('6000.00'),
            'angio': Decimal('8000.00'),
            'difusion': Decimal('8000.00'),
            'precio_unico': True,
        },
        'ECO': {
            'base_cober': Decimal('8500.00'),
            'base_otras': Decimal('10000.00'),
            'precio_unico': False,
        },
        'RAD': {
            'base': Decimal('3000.00'),
            'precio_unico': True,
        },
        'DOP': {
            'base_cober': Decimal('8500.00'),
            'base_otras': Decimal('10000.00'),
            'precio_unico': False,
        },
        'MAM': {
            'base_cober': Decimal('7000.00'),
            'base_otras': Decimal('8500.00'),
            'precio_unico': False,
        },
        'ECOCAR': {
            'base_cober': Decimal('9000.00'),
            'base_otras': Decimal('11000.00'),
            'precio_unico': False,
        },
    }
    
    # ========== MAPEO SERVICIO → TIPO ==========
    MAPEO_SERVICIO_TIPO = {
        'TOMOGRAFIA': 'TOM',
        'TOMOGRAFÍA': 'TOM',
        'TAC': 'TOM',
        'RESONANCIA': 'RES',
        'RMN': 'RES',
        'RM': 'RES',
        'ECOGRAFIA': 'ECO',
        'ECOGRAFÍA': 'ECO',
        'ECO': 'ECO',
        'RADIOGRAFIA': 'RAD',
        'RADIOGRAFÍA': 'RAD',
        'RADIOLOGIA': 'RAD',  # Radiología como servicio
        'RX': 'RAD',
        'DOPPLER': 'DOP',
        'MAMOGRAFIA': 'MAM',
        'MAMOGRAFÍA': 'MAM',
        'ECOCARDIOGRAMA': 'ECOCAR',
        'ECOCARDIO': 'ECOCAR',
    }
    
    # ========== PATRONES DE VARIANTES ==========
    PATRONES_VARIANTES = {
        'con_contraste': [
            r'\bCON\s+CONTRASTE\b',
            r'\bCON\s*/\s*CTE\b',
            r'\bCON\s+C\b',
            r'\bC/C\b',
        ],
        'sin_contraste': [
            r'\bSIN\s+CONTRASTE\b',
            r'\bSIN\s*/\s*CTE\b',
            r'\bS/C\b',
        ],
        'angio': [
            r'\bANGIO',  # Detecta ANGIO como prefijo (ANGIOTAC, ANGIOTOMOGRAFIA, etc)
            r'\bANGIOGRAFIA\b',
            r'\bANGIOGRAFÍA\b',
        ],
        'difusion': [
            r'\bDIFUSION\b',
            r'\bDIFUSIÓN\b',
        ],
    }
    
    # ========== FILTROS DE EXCLUSIÓN (MATERIALES, NO ESTUDIOS) ==========
    PATRONES_EXCLUIR = [
        r'\bAGUJA\b',
        r'^BIOPSIA\b',  # Solo si empieza con BIOPSIA
        r'\bPUNCION\b',
        r'\bPUNCIÓN\b',
        r'\bCATETER\b',
        r'\bCATÉTER\b',
        r'^CONTRASTE$',  # Solo si es exactamente "CONTRASTE" (producto aislado)
        r'\bINYECTOR\b',
        r'\bBOMBA\b',
        r'\bKIT\b',
        r'\bSUERO\b',
        r'\bFILTRO\b',
        r'\bLLAVE\b',
        r'\bJERINGA\b',
        r'\bMATERIAL\b',
        r'\bINSUMO\b',
        r'\bACCESORIO\b',
        r'\bABBOCATH\b',  # Catéter intravenoso
        r'\bANEST\b',     # Anestesia (no es estudio de imagen)
    ]
    
    def add_arguments(self, parser):
        parser.add_argument(
            'archivo',
            type=str,
            help='Ruta al archivo Excel (.xlsx)'
        )
        parser.add_argument(
            '--tipo',
            type=str,
            choices=['TOM', 'RES', 'ECO', 'RAD', 'DOP', 'MAM', 'ECOCAR', 'TODOS'],
            default='TODOS',
            help='Tipo de estudios a importar (filtra por servicio)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Modo de prueba: muestra qué se importaría sin escribir en BD'
        )
        parser.add_argument(
            '--actualizar',
            action='store_true',
            help='Actualiza estudios existentes (por código). Default: solo crear nuevos'
        )
    
    def handle(self, *args, **options):
        archivo = options['archivo']
        tipo_filtro = options['tipo']
        dry_run = options['dry_run']
        actualizar = options['actualizar']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 MODO DRY-RUN: No se escribirá en la base de datos'))
        
        self.stdout.write(self.style.NOTICE(f'📂 Leyendo archivo: {archivo}'))
        
        try:
            # Leer Excel
            df = pd.read_excel(archivo)
            self.stdout.write(self.style.SUCCESS(f'✅ Archivo leído: {len(df)} filas'))
            
            # Validar columnas requeridas
            columnas_requeridas = ['Prestación', 'Nombre', 'Servicio']
            columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
            if columnas_faltantes:
                raise CommandError(f'❌ Faltan columnas: {", ".join(columnas_faltantes)}')
            
            # Filtrar por tipo si es necesario
            if tipo_filtro != 'TODOS':
                df_original = len(df)
                df = self._filtrar_por_tipo(df, tipo_filtro)
                self.stdout.write(self.style.NOTICE(
                    f'🔎 Filtrado por tipo {tipo_filtro}: {len(df)} de {df_original} filas'
                ))
            
            # Procesar filas
            resultados = self._procesar_estudios(df, actualizar, dry_run)
            
            # Reporte final
            self._mostrar_reporte(resultados, dry_run)
            
        except FileNotFoundError:
            raise CommandError(f'❌ Archivo no encontrado: {archivo}')
        except Exception as e:
            raise CommandError(f'❌ Error al procesar: {str(e)}')
    
    def _filtrar_por_tipo(self, df, tipo):
        """Filtra el DataFrame por tipo de servicio"""
        # Buscar servicios que mapean al tipo
        servicios_validos = [
            servicio for servicio, tipo_mapeado in self.MAPEO_SERVICIO_TIPO.items()
            if tipo_mapeado == tipo
        ]
        
        # Filtrar (case insensitive)
        mascara = df['Servicio'].str.upper().str.contains(
            '|'.join(servicios_validos), 
            case=False, 
            na=False
        )
        return df[mascara]
    
    def _detectar_tipo(self, servicio, nombre):
        """Detecta el tipo de estudio desde el servicio o nombre"""
        texto = f"{servicio} {nombre}".upper()
        
        for clave, tipo in self.MAPEO_SERVICIO_TIPO.items():
            if clave in texto:
                return tipo
        
        return None
    
    def _es_material(self, nombre):
        """
        Verifica si el nombre corresponde a material/accesorio y NO a un estudio
        Retorna True si debe excluirse
        """
        nombre_upper = nombre.upper()
        return any(
            re.search(patron, nombre_upper) for patron in self.PATRONES_EXCLUIR
        )
    
    def _detectar_variantes(self, nombre):
        """
        Detecta variantes en el nombre del estudio
        Retorna dict: {'con_contraste': bool, 'angio': bool, 'difusion': bool}
        """
        nombre_upper = nombre.upper()
        variantes = {}
        
        for variante, patrones in self.PATRONES_VARIANTES.items():
            variantes[variante] = any(
                re.search(patron, nombre_upper) for patron in patrones
            )
        
        return variantes
    
    def _calcular_precios(self, tipo, variantes):
        """
        Calcula precios según tipo y variantes detectadas
        
        REGLAS ESPECIALES:
        - AngioTC: SIEMPRE lleva contraste (precio angio fijo)
        - AngioRM: Puede ser con o sin contraste (ambos mismo precio angio)
        
        Retorna: (precio_cober, precio_otras_os, precio_unico)
        """
        config = self.PRECIOS_BASE.get(tipo)
        if not config:
            return (Decimal('5000.00'), Decimal('5000.00'), True)
        
        # Estudios con precio único (TOM, RES, RAD)
        if config.get('precio_unico', False):
            # TOMOGRAFÍA
            if tipo == 'TOM':
                if variantes.get('angio'):
                    # AngioTC SIEMPRE lleva contraste implícito
                    precio = config['angio']  # $7,000
                elif variantes.get('con_contraste'):
                    precio = config.get('con_contraste', config['base'])  # $5,000
                else:
                    precio = config['base']  # $4,000
            
            # RESONANCIA
            elif tipo == 'RES':
                if variantes.get('angio'):
                    # AngioRM puede ser con o sin, pero precio es el mismo
                    precio = config['angio']  # $8,000
                elif variantes.get('difusion'):
                    precio = config.get('difusion', config['base'])  # $8,000
                elif variantes.get('con_contraste'):
                    precio = config.get('con_contraste', config['base'])  # $6,000
                else:
                    precio = config['base']  # $5,000
            
            # OTROS (RAD, etc.)
            else:
                if variantes.get('con_contraste'):
                    precio = config.get('con_contraste', config['base'])
                else:
                    precio = config['base']
            
            return (precio, precio, True)
        
        # Estudios con precio diferenciado (ECO, DOP, MAM, ECOCAR)
        else:
            precio_cober = config.get('base_cober', Decimal('5000.00'))
            precio_otras = config.get('base_otras', Decimal('5000.00'))
            return (precio_cober, precio_otras, False)
    
    def _procesar_estudios(self, df, actualizar, dry_run):
        """Procesa cada fila del DataFrame"""
        resultados = {
            'creados': [],
            'actualizados': [],
            'errores': [],
            'sin_cambios': []
        }
        
        for idx, row in df.iterrows():
            try:
                codigo = str(row.get('Prestación', '')).strip()
                nombre = str(row.get('Nombre', '')).strip()
                servicio = str(row.get('Servicio', '')).strip()
                
                if not nombre or nombre == 'nan':
                    resultados['errores'].append({
                        'fila': idx + 2,
                        'error': 'Nombre vacío',
                        'data': row.to_dict()
                    })
                    continue
                
                # Filtrar materiales/accesorios (no son estudios)
                if self._es_material(nombre):
                    resultados['errores'].append({
                        'fila': idx + 2,
                        'error': f'Material/accesorio excluido: {nombre}',
                        'data': row.to_dict()
                    })
                    continue
                
                # Detectar tipo
                tipo = self._detectar_tipo(servicio, nombre)
                if not tipo:
                    resultados['errores'].append({
                        'fila': idx + 2,
                        'error': f'No se pudo mapear servicio: {servicio}',
                        'data': row.to_dict()
                    })
                    continue
                
                # Detectar variantes
                variantes = self._detectar_variantes(nombre)
                
                # Calcular precios
                precio_cober, precio_otras_os, precio_unico = self._calcular_precios(tipo, variantes)
                
                # Preparar datos del estudio
                datos_estudio = {
                    'nombre': nombre,
                    'tipo': tipo,
                    'precio_cober': precio_cober,
                    'precio_otras_os': precio_otras_os,
                    'precio_unico': precio_unico,
                    'conteo_regiones': 1,
                    'conteo_regiones_default': 1,
                    'activo': True,
                }
                
                if codigo and codigo != 'nan':
                    datos_estudio['codigo'] = codigo
                
                # Crear o actualizar
                if not dry_run:
                    resultado = self._crear_o_actualizar_estudio(
                        datos_estudio, 
                        actualizar
                    )
                    resultados[resultado['accion']].append({
                        'nombre': nombre,
                        'codigo': codigo,
                        'tipo': tipo,
                        'precio_cober': precio_cober,
                        'variantes': variantes
                    })
                else:
                    # En dry-run, solo registrar como "creados"
                    resultados['creados'].append({
                        'nombre': nombre,
                        'codigo': codigo,
                        'tipo': tipo,
                        'precio_cober': precio_cober,
                        'variantes': variantes
                    })
                
            except Exception as e:
                resultados['errores'].append({
                    'fila': idx + 2,
                    'error': str(e),
                    'data': row.to_dict()
                })
        
        return resultados
    
    def _crear_o_actualizar_estudio(self, datos, actualizar):
        """Crea o actualiza un estudio en la BD"""
        codigo = datos.get('codigo')
        nombre = datos['nombre']
        
        # Buscar por código primero, luego por nombre
        estudio_existente = None
        if codigo:
            try:
                estudio_existente = Estudios.objects.get(codigo=codigo)
            except Estudios.DoesNotExist:
                pass
        
        if not estudio_existente:
            try:
                estudio_existente = Estudios.objects.get(nombre=nombre)
            except Estudios.DoesNotExist:
                pass
        
        # Actualizar o crear
        if estudio_existente:
            if actualizar:
                for campo, valor in datos.items():
                    setattr(estudio_existente, campo, valor)
                estudio_existente.save()
                return {'accion': 'actualizados', 'estudio': estudio_existente}
            else:
                return {'accion': 'sin_cambios', 'estudio': estudio_existente}
        else:
            estudio = Estudios.objects.create(**datos)
            return {'accion': 'creados', 'estudio': estudio}
    
    def _mostrar_reporte(self, resultados, dry_run):
        """Muestra reporte detallado de resultados"""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('📊 REPORTE DE IMPORTACIÓN'))
        self.stdout.write('=' * 60 + '\n')
        
        # Creados
        if resultados['creados']:
            self.stdout.write(self.style.SUCCESS(
                f"✅ {len(resultados['creados'])} estudios creados:"
            ))
            for item in resultados['creados'][:5]:  # Mostrar primeros 5
                variantes_str = ', '.join([k for k, v in item.get('variantes', {}).items() if v])
                variantes_info = f" [{variantes_str}]" if variantes_str else ""
                self.stdout.write(
                    f"   • {item['codigo']} - {item['nombre']} "
                    f"({item['tipo']}) - ${item['precio_cober']}{variantes_info}"
                )
            if len(resultados['creados']) > 5:
                self.stdout.write(f"   ... y {len(resultados['creados']) - 5} más")
        
        # Actualizados
        if resultados['actualizados']:
            self.stdout.write(self.style.WARNING(
                f"\n🔄 {len(resultados['actualizados'])} estudios actualizados:"
            ))
            for item in resultados['actualizados'][:5]:
                self.stdout.write(f"   • {item['codigo']} - {item['nombre']}")
            if len(resultados['actualizados']) > 5:
                self.stdout.write(f"   ... y {len(resultados['actualizados']) - 5} más")
        
        # Sin cambios
        if resultados['sin_cambios']:
            self.stdout.write(self.style.NOTICE(
                f"\n⏭️  {len(resultados['sin_cambios'])} estudios sin cambios (ya existen)"
            ))
        
        # Errores
        if resultados['errores']:
            self.stdout.write(self.style.ERROR(
                f"\n❌ {len(resultados['errores'])} errores:"
            ))
            for error in resultados['errores'][:10]:  # Mostrar primeros 10
                self.stdout.write(
                    f"   • Fila {error['fila']}: {error['error']}"
                )
            if len(resultados['errores']) > 10:
                self.stdout.write(f"   ... y {len(resultados['errores']) - 10} más")
        
        # Total
        total = (
            len(resultados['creados']) + 
            len(resultados['actualizados']) + 
            len(resultados['sin_cambios'])
        )
        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(self.style.SUCCESS(f"📈 TOTAL PROCESADOS: {total}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  Modo DRY-RUN: Ningún cambio fue aplicado a la base de datos'
            ))
            self.stdout.write(self.style.NOTICE(
                'Ejecuta sin --dry-run para aplicar los cambios'
            ))
