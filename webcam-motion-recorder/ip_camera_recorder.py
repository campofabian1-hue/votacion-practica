#!/usr/bin/env python3
"""Grabador de movimiento para cámaras IP que solo ofrecen snapshots JPEG
por HTTP (sin RTSP), como la D-Link DCS-930L.

En vez de leer un stream de video continuo, pide una foto nueva (snapshot)
repetidamente a la cámara, y aplica la misma detección de movimiento por
diferencia de frames que motion_recorder.py. Guarda los clips donde hubo
movimiento en carpetas por día, dentro de Google Drive sincronizado
localmente (mismo esquema que el grabador de la webcam).
"""

import argparse
import collections
import datetime
import io
import os
import sys
import time

import cv2
import numpy as np
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

DEFAULT_DRIVE_ROOT = (
    "/Users/mac/Library/CloudStorage/"
    "GoogleDrive-campo.fabian1@gmail.com/Mi unidad/"
    "🏠 Personal y Familia/Rec"
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--camera-ip", required=True,
                   help="IP de la cámara, ej. 192.168.1.50")
    p.add_argument("--snapshot-path", default="/image.jpg",
                   help="Ruta del snapshot JPEG en la cámara")
    p.add_argument("--username", default="admin")
    p.add_argument("--password", default="")
    p.add_argument("--camera-name", default="dlink",
                   help="Prefijo para los archivos de este camara "
                        "(para distinguirla de otras en la misma carpeta)")
    p.add_argument("--output-dir", default=DEFAULT_DRIVE_ROOT,
                   help="Carpeta raíz donde se crean las subcarpetas por día")
    p.add_argument("--poll-fps", type=float, default=3.0,
                   help="Cuántos snapshots pedir por segundo (esta cámara "
                        "no da más de unos pocos fps reales por HTTP)")
    p.add_argument("--record-fps", type=float, default=3.0,
                   help="FPS con el que se escribe el archivo de video "
                        "(debe ser cercano a --poll-fps)")
    p.add_argument("--sensitivity", type=int, default=25,
                   help="Umbral de diferencia de píxeles (más bajo = más sensible)")
    p.add_argument("--min-area", type=int, default=1500,
                   help="Área mínima en píxeles para considerar que hay movimiento")
    p.add_argument("--cooldown", type=float, default=5.0,
                   help="Segundos sin movimiento antes de cortar el clip")
    p.add_argument("--pre-roll", type=float, default=2.0,
                   help="Segundos de video previos al movimiento a incluir en el clip")
    p.add_argument("--codec", default="mp4v",
                   help="Fourcc del codec de video (mp4v, avc1, ...)")
    p.add_argument("--timeout", type=float, default=5.0,
                   help="Timeout en segundos por request HTTP a la cámara")
    return p.parse_args()


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def today_folder(root):
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(root, day)
    os.makedirs(path, exist_ok=True)
    return path


def open_writer(path, fourcc, fps, size):
    writer = cv2.VideoWriter(path, fourcc, fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"No se pudo abrir VideoWriter para {path}")
    return writer


def make_snapshot_fetcher(args):
    url = f"http://{args.camera_ip}{args.snapshot_path}"
    session = requests.Session()
    # Probamos Basic primero (lo más común en estas cámaras D-Link viejas);
    # si la cámara responde 401, cambiamos a Digest para el resto de la
    # sesión. Se detecta una sola vez y se recuerda.
    auth_mode = {"kind": "basic"}

    def fetch():
        cache_bust = int(time.time() * 1000)
        params = {"cidx": cache_bust}
        auth = (HTTPBasicAuth(args.username, args.password)
                if auth_mode["kind"] == "basic"
                else HTTPDigestAuth(args.username, args.password))
        resp = session.get(url, params=params, auth=auth,
                            timeout=args.timeout)
        if resp.status_code == 401 and auth_mode["kind"] == "basic":
            auth_mode["kind"] = "digest"
            auth = HTTPDigestAuth(args.username, args.password)
            resp = session.get(url, params=params, auth=auth,
                                timeout=args.timeout)
        resp.raise_for_status()
        content = resp.content
        # Esta cámara, cuando se le pide fotos más rápido de lo que su CPU
        # puede generar, a veces entrega un JPEG cortado a la mitad en vez
        # de fallar con un error HTTP. cv2.imdecode puede "decodificar" eso
        # igual y devolver una imagen con bloques de basura en vez de
        # lanzar una excepción, así que validamos el marcador de fin de
        # JPEG (FF D9) antes de confiar en los datos.
        if len(content) < 100 or content[-2:] != b"\xff\xd9":
            raise RuntimeError("Snapshot incompleto/corrupto (JPEG truncado)")
        data = np.frombuffer(content, dtype=np.uint8)
        frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("Snapshot recibido pero no se pudo decodificar")
        return frame

    return fetch


def get_first_frame(fetch, attempts=10, base_delay=2.0, max_delay=30.0):
    """Igual que open_camera() en motion_recorder.py: reintenta sin
    rendirse, para que un corte temporal de la cámara/red no mate el
    proceso."""
    delay = base_delay
    attempt = 0
    while True:
        attempt += 1
        try:
            return fetch()
        except Exception as exc:
            log(f"No se pudo obtener snapshot de la cámara (intento "
                f"{attempt}): {exc}. Reintentando en {delay:.0f}s...")
            time.sleep(delay)
            if attempt < attempts:
                delay = min(delay * 2, max_delay)
            else:
                delay = max_delay


def run(args):
    fetch = make_snapshot_fetcher(args)
    frame = get_first_frame(fetch)

    size = (frame.shape[1], frame.shape[0])
    fourcc = cv2.VideoWriter_fourcc(*args.codec)
    poll_interval = 1.0 / args.poll_fps

    pre_roll_frames = max(1, int(args.pre_roll * args.record_fps))
    buffer = collections.deque(maxlen=pre_roll_frames)

    prev_gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (21, 21), 0)

    writer = None
    recording = False
    last_motion_time = 0.0
    clip_frame_count = 0
    consecutive_failures = 0
    max_consecutive_failures = 8

    log(f"Grabando ({args.camera_name}) a: {args.output_dir}")
    log("Esperando movimiento... (Ctrl+C para salir)")

    try:
        while True:
            loop_start = time.time()

            try:
                frame = fetch()
                if (frame.shape[1], frame.shape[0]) != size:
                    raise RuntimeError(
                        f"Snapshot con tamaño inesperado {frame.shape[1]}x"
                        f"{frame.shape[0]} (se esperaba {size[0]}x{size[1]})")
                consecutive_failures = 0
            except Exception as exc:
                consecutive_failures += 1
                log(f"Snapshot fallido ({consecutive_failures}"
                    f"/{max_consecutive_failures}): {exc}")
                if consecutive_failures >= max_consecutive_failures:
                    log("Perdimos la cámara. Reintentando desde cero...")
                    if writer is not None:
                        writer.release()
                        writer = None
                        recording = False
                    frame = get_first_frame(fetch)
                    prev_gray = cv2.GaussianBlur(
                        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (21, 21), 0)
                    buffer.clear()
                    consecutive_failures = 0
                    log("Cámara reconectada. Esperando movimiento...")
                else:
                    time.sleep(1.0)
                    continue

            gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (21, 21), 0)
            delta = cv2.absdiff(prev_gray, gray)
            thresh = cv2.threshold(delta, args.sensitivity, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                            cv2.CHAIN_APPROX_SIMPLE)
            motion_area = sum(cv2.contourArea(c) for c in contours)
            motion_detected = motion_area > args.min_area

            prev_gray = cv2.addWeighted(prev_gray, 0.95, gray, 0.05, 0)

            now = time.time()

            if not recording:
                buffer.append(frame.copy())
                if motion_detected:
                    day_dir = today_folder(args.output_dir)
                    ts = datetime.datetime.now().strftime("%H-%M-%S")
                    out_path = os.path.join(
                        day_dir, f"{args.camera_name}_movimiento_{ts}.mp4")
                    writer = open_writer(out_path, fourcc, args.record_fps, size)
                    for buffered_frame in buffer:
                        writer.write(buffered_frame)
                    clip_frame_count = len(buffer)
                    buffer.clear()
                    recording = True
                    last_motion_time = now
                    log(f"Movimiento detectado -> grabando {out_path}")
            else:
                writer.write(frame)
                clip_frame_count += 1
                if motion_detected:
                    last_motion_time = now
                elif now - last_motion_time > args.cooldown:
                    writer.release()
                    writer = None
                    recording = False
                    duration = clip_frame_count / args.record_fps
                    log(f"Clip guardado ({duration:.1f}s). "
                        "Esperando movimiento...")

            elapsed = time.time() - loop_start
            if elapsed < poll_interval:
                time.sleep(poll_interval - elapsed)

    except KeyboardInterrupt:
        pass
    finally:
        if writer is not None:
            writer.release()
            log("Clip final guardado al salir.")
        log("Listo.")


def main():
    args = parse_args()
    while True:
        try:
            run(args)
            break
        except KeyboardInterrupt:
            break
        except Exception:
            import traceback
            log("Error inesperado, reiniciando en 5s:")
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
