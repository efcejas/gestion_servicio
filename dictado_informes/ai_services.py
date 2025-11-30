"""
Servicios de IA para dictado y mejora de informes médicos
"""
from openai import OpenAI
from django.conf import settings
from decouple import config
import logging

logger = logging.getLogger(__name__)


class AIService:
    """Servicio para integración con OpenAI"""
    
    def __init__(self):
        api_key = config('OPENAI_API_KEY', default=None)
        if api_key:
            self.client = OpenAI(api_key=api_key)
            self.enabled = True
        else:
            self.client = None
            self.enabled = False
            logger.warning("OPENAI_API_KEY no configurada. Servicios de IA deshabilitados.")
    
    def transcribe_audio(self, audio_file):
        """
        Transcribe audio usando Whisper
        
        Args:
            audio_file: Archivo de audio (FileField)
        
        Returns:
            dict: {'text': str, 'confidence': float}
        """
        if not self.enabled:
            return {
                'text': '',
                'confidence': 0.0,
                'error': 'API de OpenAI no configurada'
            }
        
        try:
            # Abrir el archivo y transcribir
            with audio_file.open('rb') as audio:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    language="es",  # Español
                    response_format="verbose_json"
                )
            
            return {
                'text': transcript.text,
                'confidence': 0.95,  # Whisper no devuelve confianza exacta
                'duration': getattr(transcript, 'duration', None)
            }
        
        except Exception as e:
            logger.error(f"Error en transcripción: {str(e)}")
            return {
                'text': '',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def improve_medical_text(self, texto_original, tipo_estudio, contexto=None):
        """
        Mejora el texto dictado usando GPT-4 para darle formato médico profesional
        
        Args:
            texto_original: Texto transcrito del audio
            tipo_estudio: Tipo de estudio (RES, TOM, etc.)
            contexto: Contexto adicional (dict con datos del paciente, etc.)
        
        Returns:
            dict: {'texto_mejorado': str, 'confianza': float, 'sugerencias': list}
        """
        if not self.enabled:
            return {
                'texto_mejorado': texto_original,
                'confianza': 0.0,
                'sugerencias': [],
                'error': 'API de OpenAI no configurada'
            }
        
        # Mapeo de tipos de estudio
        tipos_estudios = {
            'RES': 'Resonancia Magnética',
            'TOM': 'Tomografía',
            'RAD': 'Radiografía',
            'ECO': 'Ecografía',
            'MAM': 'Mamografía',
            'DEN': 'Densitometría',
            'OTR': 'Otro'
        }
        
        tipo_nombre = tipos_estudios.get(tipo_estudio, 'estudio médico')
        
        # Construir prompt para GPT
        prompt = f"""Eres un médico radiólogo experto. Tu tarea es mejorar y estructurar el siguiente texto dictado de un informe de {tipo_nombre}.

TEXTO DICTADO:
{texto_original}

INSTRUCCIONES:
1. Corrige errores gramaticales y ortográficos
2. Mejora la redacción médica profesional
3. Estructura el texto en secciones claras (Técnica, Hallazgos, Conclusión)
4. Usa terminología médica apropiada
5. Mantén la información original sin inventar datos
6. Sé conciso y claro

FORMATO DE RESPUESTA:
Proporciona el texto mejorado manteniendo la estructura profesional de un informe radiológico."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Más económico y rápido
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un médico radiólogo experto especializado en redacción de informes médicos profesionales."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Baja temperatura para mayor consistencia
                max_tokens=1500
            )
            
            texto_mejorado = response.choices[0].message.content.strip()
            
            # Calcular "confianza" basada en la longitud y coherencia
            confianza = min(0.95, len(texto_mejorado) / max(len(texto_original), 1))
            
            return {
                'texto_mejorado': texto_mejorado,
                'confianza': confianza,
                'sugerencias': self._extract_suggestions(texto_original, texto_mejorado),
                'tokens_used': response.usage.total_tokens
            }
        
        except Exception as e:
            logger.error(f"Error en mejora de texto: {str(e)}")
            return {
                'texto_mejorado': texto_original,
                'confianza': 0.0,
                'sugerencias': [],
                'error': str(e)
            }
    
    def _extract_suggestions(self, original, mejorado):
        """Extrae sugerencias comparando texto original y mejorado"""
        sugerencias = []
        
        # Análisis simple de diferencias
        if len(mejorado) > len(original) * 1.2:
            sugerencias.append("Se amplió la descripción para mayor claridad")
        
        if "TÉCNICA:" in mejorado.upper() and "TÉCNICA:" not in original.upper():
            sugerencias.append("Se añadió sección de Técnica")
        
        if "CONCLUSIÓN:" in mejorado.upper() and "CONCLUSIÓN:" not in original.upper():
            sugerencias.append("Se estructuró con Conclusión clara")
        
        return sugerencias


# Instancia global del servicio
ai_service = AIService()
