"""Publica la demo (API + página) en un Space de Hugging Face (P1.10).

Arma una carpeta mínima con lo que necesita la imagen Docker (Dockerfile, requirements de la API,
código de la API y artefactos del modelo) más el README del Space, y la sube con huggingface_hub.
Requiere la variable de entorno HF_TOKEN (token con permiso de escritura). El Space es
`<usuario>/licitaciones-desiertas` salvo que se indique HF_SPACE.

Uso: python -m compras.deploy.space [--solo-preparar carpeta]
"""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

ARCHIVOS = ["Dockerfile", "requirements-api.txt", "src/compras/__init__.py"]
CARPETAS = ["src/compras/api", "artifacts/modelo"]
NOMBRE_SPACE = "licitaciones-desiertas"


def preparar(destino: Path, raiz: Path = Path(".")) -> Path:
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    for a in ARCHIVOS:
        (destino / a).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(raiz / a, destino / a)
    for c in CARPETAS:
        shutil.copytree(raiz / c, destino / c, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(raiz / "space" / "README.md", destino / "README.md")
    return destino


def publicar(carpeta: Path, token: str, space: str | None = None) -> str:
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    repo = space or f"{api.whoami()['name']}/{NOMBRE_SPACE}"
    api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True)
    api.upload_folder(folder_path=str(carpeta), repo_id=repo, repo_type="space",
                      commit_message="Despliegue desde GitHub", delete_patterns=["*"])
    return f"https://huggingface.co/spaces/{repo}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--solo-preparar", type=Path, help="arma la carpeta y no publica")
    a = p.parse_args(argv)
    carpeta = preparar(a.solo_preparar or Path("build/space"))
    if a.solo_preparar:
        print(f"Carpeta del Space preparada en {carpeta}")
        return 0
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("Falta HF_TOKEN: no se publica el Space.")
        return 0
    print("Space publicado:", publicar(carpeta, token, os.environ.get("HF_SPACE") or None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
