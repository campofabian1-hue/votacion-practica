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
binario específico para usar la cámara. Si el log de errores muestra que no
puede abrir la cámara: ve a **Ajustes del Sistema → Privacidad y Seguridad →
Cámara** y revisa si aparece una entrada para Python (actívala); si no
aparece ninguna, corre el script una vez manualmente desde la Terminal
(como ya hiciste) para que macOS registre el permiso, y luego vuelve a
cargar el agente con `launchctl load`.

Si moviste la carpeta del proyecto a otra ruta, edita las rutas dentro de
`launchd/com.fabian.motionrecorder.plist` antes de copiarlo.

## Cómo funciona la detección de movimiento

Compara cada frame en escala de grises contra un "fondo" que se actualiza
lentamente (promedio ponderado), para tolerar cambios graduales de luz sin
perder sensibilidad a movimiento real. Cuando el área de píxeles que cambian
supera `--min-area`, empieza a grabar (incluyendo los últimos segundos antes
del movimiento, gracias al pre-roll). Sigue grabando mientras haya
movimiento, y corta el clip tras `--cooldown` segundos de quietud.
