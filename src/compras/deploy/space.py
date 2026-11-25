"""Publica la demo en un Space estático de Hugging Face (P1.10).

Arma una carpeta con la página, el evaluador del modelo en JavaScript y el modelo exportado a JSON,
más el README del Space, y la sube con huggingface_hub.
Requiere la variable de entorno HF_TOKEN (token con permiso de escritura). El Space es
`<usuario>/licitaciones-desiertas` salvo que se indique HF_SPACE.

Uso: python -m compras.deploy.space [--solo-preparar carpeta]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

NOMBRE_SPACE = "licitaciones-desiertas"
ESTATICOS = Path("src/compras/api/static")


def preparar(destino: Path, raiz: Path = Path(".")) -> Path:
    """Space estático: la página, el evaluador del modelo en JS y el modelo exportado a JSON.
    (Hugging Face cobra por los Spaces con Docker; los estáticos son gratis. Ver DECISIONS.md.)"""
    from compras.deploy.web import exportar_web

    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    for archivo in ("index.html", "modelo.js"):
        shutil.copy2(raiz / ESTATICOS / archivo, destino / archivo)
    modelo = exportar_web(raiz / "artifacts" / "modelo")
    (destino / "modelo.json").write_text(json.dumps(modelo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    shutil.copy2(raiz / "space" / "README.md", destino / "README.md")
    return destino


def publicar(carpeta: Path, token: str, space: str | None = None) -> str:
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    repo = space or f"{api.whoami()['name']}/{NOMBRE_SPACE}"
    api.create_repo(repo, repo_type="space", space_sdk="static", exist_ok=True)
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
    try:
        print("Space publicado:", publicar(carpeta, token, os.environ.get("HF_SPACE") or None))
    except Exception as e:  # noqa: BLE001 — se reporta como anotación legible en GitHub
        mensaje = str(e).replace(token, "***").replace("\n", " ")[:900]
        print(f"::error title=Publicar Space::{type(e).__name__}: {mensaje}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
