
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional

import requests
from bs4 import BeautifulSoup

SEANCES_DIRNAME = "seances"

def _iso_year_week_today() -> Tuple[int, int]:
    today = date.today()
    iso = today.isocalendar()
    return iso.year, iso.week

def _week_str(year: int, week: int) -> str:
    return f"{year}-S{week:02d}"


def _next_iso_year_week(year: int, week: int) -> Tuple[int, int]:
    monday = date.fromisocalendar(year, week, 1)
    next_monday = monday + timedelta(days=7)
    iso = next_monday.isocalendar()
    return iso.year, iso.week


def _path_or_none(p: Optional[str]) -> Optional[Path]:
    if not p:
        return None
    try:
        return Path(p)
    except Exception:
        return None


def _load_seances_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Le contenu de {path} doit être une liste JSON.")
    return data


def _save_seances_json(seances_path: Path, data: list) -> None:
    """Sauvegarde atomique simple du JSON de séances."""
    # Écriture directe (simple et suffisante ici)
    with seances_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_description(url_fiche: str) -> str:
    """Renvoie la description de la fiche associée à l'URL."""
    try:
        response = requests.get(url_fiche)
        response.raise_for_status()  # Lève une exception pour les codes d'état HTTP d'erreur
        soup = BeautifulSoup(response.text, 'html.parser')

        # Supprimer les scripts et les styles
        for script_or_style in soup(["script", "style"]):
            script_or_style.extract()

        # Extraire le texte et le nettoyer
        text = soup.get_text(separator=' ', strip=True)
        
        # Conserver une mise en page simple en remplaçant les doubles sauts de ligne
        # par des sauts de ligne simples et en nettoyant les espaces multiples.
        cleaned_text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
        return cleaned_text
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la requête HTTP vers {url_fiche}: {e}")
        return ""
    except Exception as e:
        print(f"Erreur lors de l'extraction de la description de {url_fiche}: {e}")
        return ""

def process_week(base_dir: Path, week_str: str) -> None:
    seances_path = base_dir / SEANCES_DIRNAME / f"{week_str}.json"
    if not seances_path.exists():
        print(f"[INFO] Aucun fichier trouvé pour {week_str} -> arrêt.", flush=True)
        return

    print(f"[INFO] Traitement de la semaine {week_str} ({seances_path})", flush=True)

    items = _load_seances_json(seances_path)
    if not items:
        print(f"[WARN] Aucun élément dans {seances_path}", flush=True)
        return

    for idx, item in enumerate(items, start=1):
        url_fiche_raw = item.get("url_fiche")
        if url_fiche_raw:
            url_fiche = url_fiche_raw.replace("\\", "/")
        else:
            url_fiche = None

        print(f"Trouvé URL fiche {url_fiche}", flush=True)
        if url_fiche:
            item["description"] = get_description(url_fiche)
        else:
            item["description"] = ""

    # Mise à jour du JSON de séances avec le chemin complet du fichier généré
    try:
        _save_seances_json(seances_path, items)
        print(f"[INFO] Élément {idx}: JSON mis à jour (file_youtube={item['file_youtube']}).", flush=True)
    except Exception as e:
        print(f"[WARN] Élément {idx}: échec de mise à jour du JSON: {e}", flush=True)


def main() -> int:
    base_dir = Path(__file__).resolve().parent

    year, week = _iso_year_week_today()

    # Avance semaine par semaine jusqu'à rencontrer la première semaine sans JSON, puis s'arrête.
    first_missing = False
    while not first_missing:
        wstr = _week_str(year, week)
        seances_path = base_dir / SEANCES_DIRNAME / f"{wstr}.json"
        if not seances_path.exists():
            print(f"[INFO] Aucun fichier de séances pour {wstr}. Arrêt.", flush=True)
            first_missing = True
        else:
            process_week(base_dir, wstr)
            year, week = _next_iso_year_week(year, week)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
