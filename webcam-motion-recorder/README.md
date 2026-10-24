# Webcam Motion Recorder

Grabador de cámara web que solo guarda clips cuando detecta movimiento, y los
deja organizados en carpetas por día dentro de tu Google Drive sincronizado
localmente (carpeta `Rec`). No usa la API de Google Drive ni credenciales:
simplemente escribe los archivos en la carpeta local que Google Drive para
escritorio sincroniza en segundo plano.

**Este script corre en tu Mac, no en este sandbox** (necesita acceso directo
a la cámara y a tu carpeta de Google Drive local).

## 1. Instalación

```bash
cd webcam-motion-recorder
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Permisos de cámara (macOS)

La primera vez, macOS pedirá permiso de cámara para la Terminal (o iTerm).
Si no aparece el diálogo: **Ajustes del Sistema → Privacidad y Seguridad →
Cámara**, y activa el permiso para tu terminal.

## 3. Ejecutar

```bash
python3 motion_recorder.py
```

Por defecto graba hacia:

```
/Users/mac/Library/CloudStorage/GoogleDrive-campo.fabian1@gmail.com/Mi unidad/🏠 Personal y Familia/Rec/<YYYY-MM-DD>/movimiento_HH-MM-SS.mp4
```

Verifica que esa ruta coincida con el nombre real de tu cuenta de Drive
montada (puedes confirmarlo con `ls ~/Library/CloudStorage/`). Si es
distinta, pásala con `--output-dir`:

```bash
python3 motion_recorder.py --output-dir "/ruta/a/tu/Google Drive/Rec"
```

Presiona `q` en la ventana de vista previa (o `Ctrl+C` en la terminal) para
detener.

## 4. Ajustes útiles

| Flag | Default | Qué hace |
|---|---|---|
| `--sensitivity` | 25 | Umbral de diferencia de píxeles. Más bajo = detecta movimientos más sutiles (y más falsos positivos). |
| `--min-area` | 2500 | Área mínima en píxeles para contar como "movimiento". Súbelo si detecta de más (ej. sombras, ruido de la cámara). |
| `--cooldown` | 5.0 | Segundos sin movimiento antes de cerrar el clip actual. |
| `--pre-roll` | 2.0 | Segundos de video *antes* del movimiento que se incluyen en el clip (para no perder el inicio de la acción). |
| `--fps` | 15 | FPS de captura/grabación. |
| `--width` / `--height` | 1280 / 720 | Resolución de captura. |
| `--camera-index` | 0 | Cambia si tienes varias cámaras conectadas. |
| `--no-preview` | — | Corre sin ventana (modo headless / en segundo plano). |

Ejemplo con menos sensibilidad y clips más largos:

```bash
python3 motion_recorder.py --sensitivity 35 --min-area 4000 --cooldown 8 --no-preview
```

## 5. Correr en segundo plano / al iniciar sesión

Ya incluye un `launchd` plist listo en `launchd/com.fabian.motionrecorder.plist`,
configurado para la ruta `/Users/mac/votacion-practica/webcam-motion-recorder`.

**Instalar:**

```bash
cp launchd/com.fabian.motionrecorder.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fabian.motionrecorder.plist
```

A partir de ahora arranca solo cada vez que inicias sesión en el Mac, sin
necesidad de abrir la Terminal ni la ventana de vista previa (corre con
`--no-preview`).

**Verificar que está corriendo:**

```bash
launchctl list | grep motionrecorder
tail -f ~/Library/Logs/motion-recorder.out.log
```

**Detenerlo / desinstalarlo:**

```bash
launchctl unload ~/Library/LaunchAgents/com.fabian.motionrecorder.plist
rm ~/Library/LaunchAgents/com.fabian.motionrecorder.plist
```

**Importante — permiso de cámara:** `launchd` ejecuta el `python3` del venv
directamente, no a través de la Terminal, así que macOS debe autorizar ese
binario específico para usar la cámara. Es un permiso distinto al que ya
diste cuando corriste el script manualmente la primera vez.

**Cómo saber si es este el problema:** revisa el log de errores:
```bash
tail -20 ~/Library/Logs/motion-recorder.err.log
```
Si ves estas líneas, es exactamente esto:
```
OpenCV: not authorized to capture video (status 0), requesting...
OpenCV: camera failed to properly initialize!
```
Y en el log normal (`motion-recorder.out.log`) verás "No se pudo abrir/leer
la cámara (intento N)" repitiéndose sin parar — nunca se resuelve solo,
porque no es un corte de señal sino un bloqueo de permisos.

**Cómo arreglarlo:**

```bash
# 1. Detén el agente que sigue fallando en bucle
launchctl unload ~/Library/LaunchAgents/com.fabian.motionrecorder.plist

# 2. Resetea los permisos de cámara para forzar que macOS vuelva a preguntar
tccutil reset Camera

# 3. Corre el script manualmente UNA vez, en primer plano
cd ~/votacion-practica/webcam-motion-recorder
source venv/bin/activate
python3 motion_recorder.py
```
Debe aparecer un diálogo del sistema pidiendo acceso a la cámara — dale
**"Permitir"**. Si se abre la ventana con el video, funcionó: presiona
`Ctrl+C` para detenerlo, y vuelve a cargar el agente en segundo plano:

```bash
launchctl load ~/Library/LaunchAgents/com.fabian.motionrecorder.plist
```

Verifica que quedó grabando normalmente:
```bash
tail -20 ~/Library/Logs/motion-recorder.out.log
```
Deberías ver "Esperando movimiento..." y clips guardándose, sin errores
repetidos.

## 6. Que nunca se detenga

El programa está diseñado para correr 24/7 sin pararse, con tres capas de
protección:

1. **Reconexión automática de cámara**: si falla la lectura de la cámara
   (sueño del sistema, cable USB, etc.), reintenta con espera creciente en
   vez de cerrarse.
2. **Supervisor interno**: si ocurre un error inesperado, se registra en el
   log y el programa se reinicia solo a los 5 segundos, sin salir del
   proceso.
3. **`launchd` con `KeepAlive`**: si aun así el proceso llegara a terminar
   por completo, macOS lo vuelve a lanzar automáticamente (ya actualizado
   en el plist de este repo — vuelve a copiarlo si lo instalaste antes de
   este cambio).

El plist también envuelve el programa con `caffeinate -ism`, para evitar
que el Mac entre en reposo por inactividad mientras graba (no hace falta
mantener la pantalla encendida). **Si tu Mac tiene un horario de apagado o
suspensión programado** (Ajustes del Sistema → Energía → "Horario"),
`caffeinate` no lo anula — desactiva ese horario si quieres grabación
realmente continua.

Si ya tenías el `launchd` cargado desde antes, actualízalo así para que
tome el plist nuevo:

```bash
launchctl unload ~/Library/LaunchAgents/com.fabian.motionrecorder.plist
cp launchd/com.fabian.motionrecorder.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fabian.motionrecorder.plist
```

Si moviste la carpeta del proyecto a otra ruta, edita las rutas dentro de
`launchd/com.fabian.motionrecorder.plist` antes de copiarlo.

## 7. Cámara IP sin RTSP (ej. D-Link DCS-930L)

Algunas cámaras IP viejas (como la D-Link DCS-930L) no soportan RTSP, solo
dan una foto (snapshot JPEG) por HTTP que su propia página web refresca
repetidamente para simular "video en vivo". `ip_camera_recorder.py` hace lo
mismo por su cuenta: pide un snapshot nuevo varias veces por segundo y le
aplica la misma detección de movimiento que `motion_recorder.py`, guardando
los clips en la misma estructura de carpetas por día en Drive (con un
prefijo distinto en el nombre del archivo para no mezclarlas con las de la
webcam, ej. `dlink_movimiento_HH-MM-SS.mp4`).

**Cómo se encontraron la IP y la contraseña de la cámara (dejar constancia
por si se resetea de nuevo):**
1. La D-Link DCS-930L no crea su propia red WiFi para configurarse — hay
   que conectarla por **cable Ethernet** al router la primera vez.
2. Una vez conectada por cable, aparece en el panel de "Dispositivos
   conectados" del router (app Tether de TP-Link, en este caso) con su IP.
   Puede estar en un rango distinto al de la WiFi principal (ej.
   `192.168.0.x` en vez de `192.168.1.x`) — si es así, conéctate
   temporalmente a la red WiFi del mismo router (no a la principal) para
   poder abrir su página de configuración.
3. Usuario `admin`, contraseña en blanco (default de fábrica tras el
   reset). **Esto solo funciona recién reseteada** — si ya tiene
   contraseña puesta, no sirve.
4. Desde "CONFIGURATION → Wireless Setup" se le asigna la WiFi definitiva
   (la misma red que usa el resto de la casa), para que quede en el mismo
   rango de IP que el Mac y no dependa del cable.
5. La URL del snapshot se obtiene inspeccionando la página de video en
   vivo (clic derecho sobre la imagen → "Abrir imagen en pestaña nueva"):
   quedó en `/image.jpg` con un parámetro `cidx` que cambia cada vez
   (cache-busting) — el script lo regenera automáticamente en cada
   request, no hace falta tocarlo.

**Instalar y correr manualmente (una vez, para confirmar que funciona y
que macOS pida el permiso correspondiente si aplica):**

```bash
cd webcam-motion-recorder
source venv/bin/activate
python3 ip_camera_recorder.py --camera-ip <IP_DE_LA_CAMARA>
```

Si todo va bien, verás "Esperando movimiento..." y clips guardándose en
Drive igual que con la webcam. Prueba moviéndote frente a la cámara.

**Dejarla corriendo en segundo plano:** hay un `launchd` plist en
`launchd/com.fabian.dlinkrecorder.plist` — antes de instalarlo, edita el
archivo y reemplaza `REEMPLAZA_CON_LA_IP` por la IP real de la cámara (una
vez que ya esté en la WiFi definitiva, para que no cambie). Luego:

```bash
cp launchd/com.fabian.dlinkrecorder.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.fabian.dlinkrecorder.plist
```

Corre en paralelo e independiente del grabador de la webcam (los dos
`launchd` pueden estar cargados al mismo tiempo sin chocar, cada uno con
su propio log):

```bash
tail -f ~/Library/Logs/dlink-recorder.out.log
```

**Si la cámara cambia de IP** (ej. el router reasigna direcciones), hay
que actualizar `--camera-ip` en el plist, recargarlo (`unload` + editar +
`load`), o fijarle una IP reservada/estática en la configuración del
router para que esto no vuelva a pasar.

## Cómo funciona la detección de movimiento

Compara cada frame en escala de grises contra un "fondo" que se actualiza
lentamente (promedio ponderado), para tolerar cambios graduales de luz sin
perder sensibilidad a movimiento real. Cuando el área de píxeles que cambian
supera `--min-area`, empieza a grabar (incluyendo los últimos segundos antes
del movimiento, gracias al pre-roll). Sigue grabando mientras haya
movimiento, y corta el clip tras `--cooldown` segundos de quietud.
