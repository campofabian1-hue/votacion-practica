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

## Cómo funciona la detección de movimiento

Compara cada frame en escala de grises contra un "fondo" que se actualiza
lentamente (promedio ponderado), para tolerar cambios graduales de luz sin
perder sensibilidad a movimiento real. Cuando el área de píxeles que cambian
supera `--min-area`, empieza a grabar (incluyendo los últimos segundos antes
del movimiento, gracias al pre-roll). Sigue grabando mientras haya
movimiento, y corta el clip tras `--cooldown` segundos de quietud.
