## Mantener activa la sesión para la extracción

1. Conéctate por RDP con `observatorio.ino`.

2. Al terminar, abre PowerShell como administrador y consulta el ID de la sesión:

```powershell
query session
```

3. Actualiza la tarea reemplazando `<ID>` por el ID de `observatorio.ino`:

```powershell
schtasks /change /tn "Transferir observatorio a consola" /tr "C:\Windows\System32\tscon.exe <ID> /dest:console"
```

4. Transfiere la sesión a la consola:

```powershell
schtasks /run /tn "Transferir observatorio a consola"
```

La conexión RDP se cerrará automáticamente. No uses **Cerrar sesión**. Después de reiniciar el servidor, repite el procedimiento.
