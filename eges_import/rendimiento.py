"""Mediciones agregadas del tablero, sin contenido de los estudios."""
import logging
import os
import sys
from time import perf_counter
from uuid import uuid4


logger = logging.getLogger('django.eges_import.rendimiento')


def memoria_proceso():
    """Devuelve memoria residente actual y pico del proceso, en MiB."""
    try:
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes

            class Contadores(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('fallos', wintypes.DWORD)] + [
                    (nombre, ctypes.c_size_t) for nombre in (
                        'pico', 'actual', 'pico_paginado', 'paginado',
                        'pico_no_paginado', 'no_paginado', 'archivo', 'pico_archivo',
                    )
                ]

            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            consulta = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
            consulta.argtypes = [wintypes.HANDLE, ctypes.POINTER(Contadores), wintypes.DWORD]
            consulta.restype = wintypes.BOOL
            datos = Contadores()
            datos.cb = ctypes.sizeof(datos)
            if not consulta(kernel.GetCurrentProcess(), ctypes.byref(datos), datos.cb):
                return None, None
            return round(datos.actual / 1048576, 2), round(datos.pico / 1048576, 2)
        if sys.platform.startswith('linux'):
            with open('/proc/self/status', encoding='ascii') as archivo:
                valores = {linea.split(':', 1)[0]: int(linea.split()[1])
                           for linea in archivo if linea.startswith(('VmRSS:', 'VmHWM:'))}
            return round(valores['VmRSS'] / 1024, 2), round(valores['VmHWM'] / 1024, 2)
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    return None, None


class MedicionEstadisticas:
    def __init__(self):
        self.consulta = uuid4().hex[:12]
        self.inicio = self.anterior = perf_counter()
        self.marcar('inicio')

    def marcar(self, etapa):
        ahora = perf_counter()
        residente, pico = memoria_proceso()
        logger.info(
            'estadisticas_rendimiento consulta=%s pid=%s etapa=%s '
            'etapa_ms=%.1f total_ms=%.1f rss_mib=%s pico_rss_mib=%s',
            self.consulta, os.getpid(), etapa, (ahora - self.anterior) * 1000,
            (ahora - self.inicio) * 1000, residente, pico,
        )
        self.anterior = perf_counter()
