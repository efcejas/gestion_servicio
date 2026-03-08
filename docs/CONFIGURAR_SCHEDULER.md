# 🚀 INSTALACIÓN RÁPIDA DEL TASK SCHEDULER

## Opción 1: Script Automático (Recomendado) ⚡

1. **Abre PowerShell como Administrador:**
   - Presiona `Win + X`
   - Selecciona "Windows PowerShell (Admin)" o "Terminal (Admin)"

2. **Navega al directorio:**
   ```powershell
   cd C:\Dev\GitHub\gestion_servicio
   ```

3. **Ejecuta el configurador:**
   ```powershell
   .\configurar_task_scheduler.ps1
   ```

4. **Sigue las instrucciones en pantalla**
   - El script creará la tarea automáticamente
   - Te preguntará si quieres hacer una prueba

**¡Listo!** El sistema procesará emails cada 5 minutos automáticamente.

---

## Opción 2: Configuración Manual 🔧

Si el script automático no funciona, sigue estos pasos:

1. Presiona `Win + R` → escribe `taskschd.msc` → Enter

2. Panel derecho → "Crear tarea" (NO "Crear tarea básica")

3. **Pestaña General:**
   - Nombre: `ProcesarPedidosEstudios`
   - Descripción: `Procesa pedidos de estudios desde Gmail cada 5 minutos`
   - Configurar para: Windows 10/11
   - ✅ Ejecutar con los privilegios más altos

4. **Pestaña Desencadenadores → Nuevo:**
   - Comenzar la tarea: Una vez
   - Fecha/hora: Hoy a las [hora actual]
   - ✅ Repetir la tarea cada: **5 minutos**
   - Durante: Indefinidamente
   - ✅ Habilitado

5. **Pestaña Acciones → Nuevo:**
   - Acción: Iniciar un programa
   - Programa: `C:\Dev\GitHub\gestion_servicio\procesar_pedidos_auto.bat`
   - Comenzar en: `C:\Dev\GitHub\gestion_servicio`

6. **Pestaña Condiciones:**
   - ❌ Desmarcar "Iniciar la tarea solo si el equipo está con alimentación CA"

7. **Pestaña Configuración:**
   - ✅ Permitir ejecutar tarea a petición
   - ✅ Ejecutar la tarea lo antes posible después de perder una ejecución programada
   - Si la tarea en ejecución no finaliza cuando se solicita, forzar su detención: Sí
   - Si la tarea ya se está ejecutando: No iniciar una nueva instancia

8. **Aceptar** → Listo

---

## ✅ Verificar que Funciona

**Opción A - Ejecutar manualmente:**
1. Abre Task Scheduler (`taskschd.msc`)
2. Busca "ProcesarPedidosEstudios"
3. Clic derecho → "Ejecutar"
4. Revisa el log: `type logs\procesar_pedidos.log`

**Opción B - Enviar email de prueba:**
1. Envía un email a: solicitudestudioscolegiales@gmail.com
2. Espera 5 minutos (o ejecuta manualmente)
3. Verifica en Django admin que se creó el pedido

---

## 📝 Ver Logs de Ejecución

```powershell
# Ver log del sistema
type logs\procesar_pedidos.log

# Ver en tiempo real
Get-Content logs\procesar_pedidos.log -Wait

# Ver últimas 20 líneas
Get-Content logs\procesar_pedidos.log -Tail 20
```

---

## 🔧 Ajustar Frecuencia

Para cambiar de 5 minutos a otra frecuencia:

1. Abre Task Scheduler (`taskschd.msc`)
2. Busca "ProcesarPedidosEstudios"
3. Clic derecho → Propiedades
4. Pestaña Desencadenadores → Editar
5. Cambia "Repetir cada" a tu preferencia:
   - **3 minutos** - Alta frecuencia (muchos pedidos)
   - **5 minutos** - Recomendado para producción
   - **10 minutos** - Frecuencia normal
   - **30 minutos** - Baja frecuencia (pocos pedidos)

---

## 🛑 Desactivar/Eliminar Tarea

**Desactivar temporalmente:**
```powershell
Disable-ScheduledTask -TaskName "ProcesarPedidosEstudios"
```

**Reactivar:**
```powershell
Enable-ScheduledTask -TaskName "ProcesarPedidosEstudios"
```

**Eliminar:**
```powershell
Unregister-ScheduledTask -TaskName "ProcesarPedidosEstudios" -Confirm:$false
```

---

## ❓ Troubleshooting

**La tarea no se ejecuta:**
- Verifica que esté habilitada en Task Scheduler
- Verifica que "Ejecutar en ejecución perdida" esté marcado
- Revisa el historial en Task Scheduler → pestaña Historial

**Errores en el log:**
- Verifica que el entorno virtual existe: `gestion_env\Scripts\python.exe`
- Verifica permisos de escritura en carpeta `logs`
- Ejecuta manualmente el .bat para ver errores: `procesar_pedidos_auto.bat`

**No marca emails como leídos:**
- El comando automático (`procesar_pedidos_auto`) SÍ marca como leídos
- Verifica que `token.json` tenga permisos de gmail.modify

---

## 📊 Monitoreo en Producción

Ver estado de la tarea:
```powershell
Get-ScheduledTask -TaskName "ProcesarPedidosEstudios" | Format-List *
```

Ver última ejecución:
```powershell
Get-ScheduledTaskInfo -TaskName "ProcesarPedidosEstudios"
```

Ver historial de ejecuciones:
- Abrir Task Scheduler
- Seleccionar la tarea
- Pestaña "Historial"
