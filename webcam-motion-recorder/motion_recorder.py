#!/usr/bin/env python3
"""Grabador de webcam con detección de movimiento.

Captura video de la cámara, detecta movimiento por diferencia de frames,
y guarda únicamente los clips donde hubo movimiento como archivos .mp4
dentro de una carpeta con la fecha del día (YYYY-MM-DD), dentro de la
carpeta raíz indicada (por defecto, la carpeta "Rec" dentro de Google Drive
sincronizado localmente). Google Drive para escritorio sube esos archivos
automáticamente: no se usa la API de Drive ni credenciales de Google Cloud.
"""

import argparse
import collections
import datetime
import os
import sys
import time

import cv2
import numpy as np

DEFAULT_DRIVE_ROOT = (
    "/Users/mac/Library/CloudStorage/"
    "GoogleDrive-campo.fabian1@gmail.com/Mi unidad/"
    "🏠 Personal y Familia/Rec"
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", default=DEFAULT_DRIVE_ROOT,
                   help="Carpeta raíz donde se crean las subcarpetas por día")
    p.add_argument("--camera-index", type=int, default=0,
                   help="Índice de la cámara (0 = cámara por defecto)")
    p.add_argument("--fps", type=float, default=15.0,
                   help="FPS objetivo de captura y grabación")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--sensitivity", type=int, default=25,
                   help="Umbral de diferencia de píxeles (más bajo = más sensible)")
    p.add_argument("--min-area", type=int, default=2500,
                   help="Área mínima en píxeles para considerar que hay movimiento")
    p.add_argument("--cooldown", type=float, default=5.0,
                   help="Segundos sin movimiento antes de cortar el clip")
    p.add_argument("--pre-roll", type=float, default=2.0,
                   help="Segundos de video previos al movimiento a incluir en el clip")
    p.add_argument("--codec", default="mp4v",
                   help="Fourcc del codec de video (mp4v, avc1, ...)")
    p.add_argument("--no-preview", action="store_true",
                   help="No mostrar ventana de vista previa (modo headless)")
    return p.parse_args()


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


def main():
    args = parse_args()

    cap = cv2.VideoCapture(args.camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    if not cap.isOpened():
        print("No se pudo abrir la cámara. Revisa permisos de cámara "
              "(macOS: Ajustes > Privacidad y seguridad > Cámara).",
              file=sys.stderr)
        sys.exit(1)

    ok, frame = cap.read()
    if not ok:
        print("La cámara no entregó ningún frame.", file=sys.stderr)
        sys.exit(1)

    size = (frame.shape[1], frame.shape[0])
    fourcc = cv2.VideoWriter_fourcc(*args.codec)

    pre_roll_frames = max(1, int(args.pre_roll * args.fps))
    buffer = collections.deque(maxlen=pre_roll_frames)

    prev_gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (21, 21), 0)

    writer = None
    recording = False
    last_motion_time = 0.0
    clip_frame_count = 0

    print(f"Grabando a: {args.output_dir}")
    print("Esperando movimiento... (Ctrl+C para salir)")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Se perdió la señal de la cámara.", file=sys.stderr)
                break

            gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (21, 21), 0)
            delta = cv2.absdiff(prev_gray, gray)
            thresh = cv2.threshold(delta, args.sensitivity, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                            cv2.CHAIN_APPROX_SIMPLE)
            motion_area = sum(cv2.contourArea(c) for c in contours)
            motion_detected = motion_area > args.min_area

            # Actualizar el fondo de referencia lentamente para adaptarse a
            # cambios de luz, sin perder sensibilidad al movimiento real.
            prev_gray = cv2.addWeighted(prev_gray, 0.95, gray, 0.05, 0)

            now = time.time()

            if not recording:
                buffer.append(frame.copy())
                if motion_detected:
                    day_dir = today_folder(args.output_dir)
                    ts = datetime.datetime.now().strftime("%H-%M-%S")
                    out_path = os.path.join(day_dir, f"movimiento_{ts}.mp4")
                    writer = open_writer(out_path, fourcc, args.fps, size)
                    for buffered_frame in buffer:
                        writer.write(buffered_frame)
                    clip_frame_count = len(buffer)
                    buffer.clear()
                    recording = True
                    last_motion_time = now
                    print(f"[{ts}] Movimiento detectado -> grabando {out_path}")
            else:
                writer.write(frame)
                clip_frame_count += 1
                if motion_detected:
                    last_motion_time = now
                elif now - last_motion_time > args.cooldown:
                    writer.release()
                    writer = None
                    recording = False
                    duration = clip_frame_count / args.fps
                    print(f"  Clip guardado ({duration:.1f}s). "
                          "Esperando movimiento...")

            if not args.no_preview:
                display = frame.copy()
                if recording:
                    cv2.circle(display, (20, 20), 8, (0, 0, 255), -1)
                    cv2.putText(display, "REC", (35, 28),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.imshow("Motion Recorder (q para salir)", display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        pass
    finally:
        if writer is not None:
            writer.release()
            print("Clip final guardado al salir.")
        cap.release()
        cv2.destroyAllWindows()
        print("Listo.")


if __name__ == "__main__":
    main()
