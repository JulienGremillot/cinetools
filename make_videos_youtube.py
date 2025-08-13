# -*- coding: utf-8 -*-
"""
Génère des vidéos prêtes pour YouTube en concaténant chaque bande-annonce
avec 5 secondes du carton (image fixe + silence), semaine par semaine,
en partant de la semaine ISO courante puis en avançant d'une semaine tant
que le fichier JSON seances/YYYY-SWW.json existe.

Commande ffmpeg utilisée (schéma):
ffmpeg -y -i "<bande_annonce.mp4>" -loop 1 -t 5 -i "<carton.png>" -f lavfi -t 5 -i anullsrc \
  -filter_complex "[0:v] [0:a] [1:v] [2:a] concat=n=2:v=1:a=1 [v] [a]" \
  -c:v libx264 -c:a aac -strict -2 -map "[v]" -map "[a]" "<videos_youtube/YYYY-SWW/<nom>.mp4>"
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional


STILL_DURATION_SECONDS = 5  # durée du carton (image fixe + silence)
SEANCES_DIRNAME = "seances"
OUTPUT_BASE_DIRNAME = "videos_youtube"


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


def _sanitize_filename(name: str, default_ext: str = ".mp4") -> str:
    # Remplace les caractères problématiques par des underscores.
    # Conserve l'extension fournie si name ne l'a pas déjà.
    invalid = '<>:"/\\|?*\n\r\t'
    sanitized = "".join(c if c not in invalid else "_" for c in name).strip()
    if not sanitized:
        sanitized = "video"
    if "." not in Path(sanitized).name:
        sanitized += default_ext
    return sanitized


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _build_ffmpeg_command(
    ba_path: Path,
    carton_path: Path,
    out_path: Path,
    still_duration: int = STILL_DURATION_SECONDS,
) -> List[str]:
    # Construire la commande telle que demandée (sans quoting manuel).
    # Note: on suit strictement l'exemple fourni.
    return [
        "ffmpeg", "-y",
        "-i", str(ba_path),  # Vidéo bande-annonce
        "-vsync", "2",  # <- clé pour éviter les duplications massives
        "-loop", "1", "-t", str(still_duration), "-i", str(carton_path),  # Carton fixe 5 sec
        "-f", "lavfi", "-t", str(still_duration), "-i", "anullsrc",  # Silence 5 sec pour carton
        # Harmonisation du framerate et format du carton avant concat
        "-filter_complex",
        "[1:v]fps=25,format=yuv420p[v1];"  # Carton : 25 fps, format standard
        "[0:v][0:a][v1][2:a]concat=n=2:v=1:a=1[v][a]",
        "-c:v", "libx264", "-preset", "fast",  # Encodage vidéo rapide
        "-c:a", "aac", "-b:a", "128k",  # Audio AAC
        "-map", "[v]", "-map", "[a]",
        str(out_path)
    ]


def _load_seances_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Le contenu de {path} doit être une liste JSON.")
    return data


def _resolve_output_filename(item: Dict[str, Any]) -> str:
    # Priorité au nom de la bande-annonce s'il est disponible.
    ba = item.get("file_bandeannonce")
    if isinstance(ba, str) and ba.strip():
        name = Path(ba).name
        # S'assurer d'une extension .mp4
        if not name.lower().endswith(".mp4"):
            name = Path(name).with_suffix(".mp4").name
        return name
    # Sinon, dériver du titre.
    titre = item.get("titre") or "video"
    return _sanitize_filename(str(titre), default_ext=".mp4")


def _path_or_none(p: Optional[str]) -> Optional[Path]:
    if not p:
        return None
    try:
        return Path(p)
    except Exception:
        return None


def process_week(base_dir: Path, week_str: str) -> None:
    seances_path = base_dir / SEANCES_DIRNAME / f"{week_str}.json"
    if not seances_path.exists():
        print(f"[INFO] Aucun fichier trouvé pour {week_str} -> arrêt.", flush=True)
        return

    print(f"[INFO] Traitement de la semaine {week_str} ({seances_path})", flush=True)
    output_dir = base_dir / OUTPUT_BASE_DIRNAME / week_str
    output_dir.mkdir(parents=True, exist_ok=True)

    items = _load_seances_json(seances_path)
    if not items:
        print(f"[WARN] Aucun élément dans {seances_path}", flush=True)
        return

    for idx, item in enumerate(items, start=1):
        ba_path = _path_or_none(item.get("file_bandeannonce"))
        carton_path = _path_or_none(item.get("file_carton"))
        out_name = _resolve_output_filename(item)
        out_path = output_dir / out_name

        # Ne pas lancer le traitement si la sortie existe déjà
        if out_path.exists():
            print(f"[INFO] Fichier déjà présent, saut de l'élément {idx}: {out_path}", flush=True)
            continue

        # Vérifications minimales
        missing = []
        if not ba_path or not ba_path.exists():
            missing.append("file_bandeannonce")
        if not carton_path or not carton_path.exists():
            missing.append("file_carton")

        if missing:
            print(f"[WARN] Élément {idx}: champs manquants ou fichiers introuvables: {', '.join(missing)}. Saut...", flush=True)
            continue

        cmd = _build_ffmpeg_command(ba_path, carton_path, out_path)
        print(f"[INFO] Élément {idx}: ffmpeg -> {out_path.name}", flush=True)

        try:
            # Pour de meilleures performances, on évite la capture des sorties.
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] ffmpeg a échoué pour {out_path.name} (code {e.returncode}).", flush=True)
        except Exception as e:
            print(f"[ERROR] Erreur inattendue pour {out_path.name}: {e}", flush=True)


def main(argv: List[str]) -> int:
    base_dir = Path(__file__).resolve().parent

    if not _ffmpeg_available():
        print("[ERROR] ffmpeg n'est pas disponible dans le PATH. Veuillez l'installer et réessayer.", file=sys.stderr)
        return 1

    # Donne la version de ffmpeg
    subprocess.run(["ffmpeg", "-version"])

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
    raise SystemExit(main(sys.argv[1:]))
