"""Descarga un modelo/dataset entrenado desde un proyecto de Roboflow Universe.

Genérico a propósito: no está atado a un proyecto en particular, así sirve
para probar cualquier modelo público que aparezca (rodent detection u
otro) sin tener que escribir un script nuevo cada vez.

Requiere ROBOFLOW_API_KEY en server/.env (ver .env.example — se genera en
roboflow.com -> Settings -> API Key).

Uso (desde server/, con el extra "roboflow" instalado):
    uv sync --extra roboflow
    uv run --extra roboflow python scripts/download_roboflow_model.py \
        --workspace winter-zebrafish-test --project did-rodent-yolov8 --version 1

El workspace/project salen de la URL de Roboflow Universe:
    universe.roboflow.com/<workspace>/<project>
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", required=True, help="Slug del workspace (de la URL de Universe)")
    parser.add_argument("--project", required=True, help="Slug del proyecto (de la URL de Universe)")
    parser.add_argument("--version", type=int, default=1, help="Número de versión del dataset/modelo (default: 1)")
    parser.add_argument(
        "--format",
        default="yolov8",
        help="Formato de descarga: yolov8 (default), yolov11, coco, etc.",
    )
    args = parser.parse_args()

    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        print(
            "Falta ROBOFLOW_API_KEY en server/.env "
            "(generarla en roboflow.com -> Settings -> API Key)",
            file=sys.stderr,
        )
        return 1

    try:
        from roboflow import Roboflow
    except ImportError:
        print(
            "Falta el paquete 'roboflow'. Instalalo con: uv sync --extra roboflow",
            file=sys.stderr,
        )
        return 1

    print(f"Conectando a Roboflow (workspace={args.workspace}, project={args.project})...")
    rf = Roboflow(api_key=api_key)

    try:
        project = rf.workspace(args.workspace).project(args.project)
        version = project.version(args.version)
    except Exception as exc:  # noqa: BLE001 - script de un solo uso, el SDK de roboflow no documenta que tipos de excepcion lanza
        print(f"No se pudo acceder a {args.workspace}/{args.project} v{args.version}: {exc}", file=sys.stderr)
        print(
            "Revisá el workspace/project (salen de la URL de Roboflow Universe) "
            "y el número de versión en la pestaña 'Versions' del proyecto.",
            file=sys.stderr,
        )
        return 1

    print(f"Descargando en formato '{args.format}' (puede tardar un rato)...")
    dataset = version.download(args.format)

    print(f"\nListo. Contenido descargado en: {dataset.location}")
    print(
        "Buscá ahí un archivo de pesos (best.pt / weights.pt) — si aparece, "
        "apuntá YOLO_MODEL_PATH en server/.env a esa ruta. Si solo bajaron "
        "imágenes + labels (sin .pt), este proyecto no publica pesos "
        "descargables y haría falta entrenar localmente con ese dataset."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
