# Python
from __future__ import annotations

import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from common import sanitize_filename


def extension_from_url(url: str) -> str:
    """
    Extrait l'extension (avec le point) depuis l'URL si présente.
    Exemple: '.../image.jpg?x=1' -> '.jpg'
    """
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext.lower()


def extension_from_content_type(content_type: Optional[str]) -> str:
    """
    Déduit une extension de fichier depuis un Content-Type HTTP.
    """
    if not content_type:
        return ""
    content_type = content_type.split(";")[0].strip().lower()
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "image/tiff": ".tiff",
        "image/x-icon": ".ico",
        "image/svg+xml": ".svg",
    }
    if content_type in mapping:
        return mapping[content_type]

    # Fallback via mimetypes
    ext = mimetypes.guess_extension(content_type)
    return ext or ""


def ensure_unique_path(path: Path) -> Path:
    """
    Si un fichier existe déjà, ajoute un suffixe ' (1)', ' (2)', etc.
    """
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def download_poster(url: str, dest_path: Path, session: Optional[requests.Session] = None) -> Path:
    """
    Télécharge le contenu de `url` vers `dest_path`.
    Si dest_path n'a pas d'extension, tente de la déterminer via Content-Type.
    Retourne le chemin final écrit.
    """
    s = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PosterFetcher/1.0)"
    }

    # Déterminer l'extension depuis l'URL si manquante
    final_path = dest_path
    if not final_path.suffix:
        # On tentera de fixer après HEAD/GET si possible
        pass

    # Faire une requête GET en streaming
    with s.get(url, headers=headers, timeout=30, stream=True) as resp:
        resp.raise_for_status()

        # Si aucune extension, essayer de la déduire du Content-Type
        if not final_path.suffix:
            ext = extension_from_content_type(resp.headers.get("Content-Type"))
            if ext:
                final_path = final_path.with_suffix(ext)

        # S'assurer de l'unicité du nom
        final_path = ensure_unique_path(final_path)

        # Écrire par chunks
        final_path.parent.mkdir(parents=True, exist_ok=True)
        with open(final_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    return final_path


def process_json_file(json_path: Path, posters_root: Path, session: requests.Session) -> None:
    """
    Lit un fichier JSON et télécharge les posters dans posters_root/<nom_json_sans_ext>/.
    Ajoute pour chaque objet un attribut "file_poster" pointant vers le chemin local du fichier.
    """
    subdir = posters_root / json_path.stem
    subdir.mkdir(parents=True, exist_ok=True)

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERREUR] Impossible de lire {json_path.name}: {e}", file=sys.stderr)
        return

    if not isinstance(data, list):
        print(f"[AVERTISSEMENT] Le JSON racine de {json_path.name} n'est pas un tableau. Ignoré.", file=sys.stderr)
        return

    changed = False

    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            print(f"[AVERTISSEMENT] Élément #{idx} de {json_path.name} n'est pas un objet. Ignoré.", file=sys.stderr)
            continue

        titre = item.get("titre")
        url = item.get("url_poster")

        if not titre or not url:
            print(f"[AVERTISSEMENT] Élément #{idx} de {json_path.name} sans 'titre' ou 'url_poster'. Ignoré.", file=sys.stderr)
            continue

        safe_name = sanitize_filename(titre)

        # Conserver l'extension d'origine de l'URL si disponible
        ext = extension_from_url(url)
        dest = subdir / f"{safe_name}{ext}"

        final_path: Path | None = None

        # Si un fichier avec le même nom existe, on saute (déjà téléchargé) mais on renseigne "file_poster"
        if dest.exists():
            final_path = dest
            print(f"[INFO] Déjà présent: {dest.relative_to(posters_root)}")
        else:
            # Si pas d'extension dans l'URL, `download_poster` tentera via Content-Type
            try:
                final_path = download_poster(url, dest, session=session)
                rel = final_path.relative_to(posters_root)
                print(f"[OK] {rel}")
            except requests.HTTPError as e:
                print(f"[ERREUR HTTP] {json_path.name} :: '{titre}': {e}", file=sys.stderr)
            except requests.RequestException as e:
                print(f"[ERREUR RÉSEAU] {json_path.name} :: '{titre}': {e}", file=sys.stderr)
            except Exception as e:
                print(f"[ERREUR] {json_path.name} :: '{titre}': {e}", file=sys.stderr)

        # Si on a un chemin de fichier valide, on met à jour l'objet JSON
        if final_path is not None:
            item["file_poster"] = str(final_path)
            changed = True

    # Si des éléments ont été mis à jour, on réécrit le fichier JSON
    if changed:
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERREUR] Impossible d'écrire {json_path.name}: {e}", file=sys.stderr)


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    seances_dir = base_dir / "seances"
    posters_dir = base_dir / "posters"

    if not seances_dir.exists():
        print(f"[ERREUR] Le répertoire 'seances' est introuvable à {seances_dir}", file=sys.stderr)
        sys.exit(1)

    posters_dir.mkdir(exist_ok=True)

    json_files = sorted(seances_dir.glob("*.json"))
    if not json_files:
        print(f"[INFO] Aucun fichier JSON trouvé dans {seances_dir}")
        return

    with requests.Session() as session:
        session.headers.update({"Accept": "*/*"})
        for json_path in json_files:
            print(f"[TRAITEMENT] {json_path.name}")
            process_json_file(json_path, posters_dir, session=session)

    print("[TERMINE]")


if __name__ == "__main__":
    main()