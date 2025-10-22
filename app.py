import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from flask import Flask, jsonify, send_from_directory


BASE_DIR = Path(__file__).parent.resolve()
SEANCES_DIR = BASE_DIR / "seances"
BANDES_ANNONCES_DIR = BASE_DIR / "bandes_annonces"
CARTONS_DIR = BASE_DIR / "cartons"
VIDEOS_YOUTUBE_DIR = BASE_DIR / "videos_youtube"
POSTERS_DIR = BASE_DIR / "posters"
STATIC_DIR = BASE_DIR / "static"


app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/")


WEEK_FILE_PATTERN = re.compile(r"^(\d{4})-S(\d{2})\.json$")


def parse_week_from_filename(filename: str) -> tuple[int, int]:
    match = WEEK_FILE_PATTERN.match(filename)
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2)))


def load_week_file(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def file_exists(path_str: str | None) -> bool:
    if not path_str:
        return False
    try:
        return Path(path_str).exists()
    except Exception:
        return False


def build_week_payload(week_file: Path) -> Dict[str, Any]:
    year, week = parse_week_from_filename(week_file.name)
    try:
        films = load_week_file(week_file)
    except Exception:
        films = []

    items: List[Dict[str, Any]] = []
    for film in films:
        titre = film.get("titre")
        description = film.get("description")
        seances = film.get("seances", [])
        file_ba = film.get("file_bandeannonce")
        file_carton = film.get("file_carton")
        file_yt = film.get("file_youtube")
        url_yt = film.get("url_youtube")
        file_poster = film.get("file_poster")

        items.append({
            "titre": titre,
            "description": description,
            "seances": seances,
            "poster": file_poster,
            "status": {
                "bande_annonce": bool(file_exists(file_ba)),
                "carton": bool(file_exists(file_carton)),
                "youtube_file": bool(file_exists(file_yt)),
                "youtube_sent": bool(url_yt),
            },
            "links": {
                "youtube": url_yt,
            }
        })

    # Trier films par première séance si dispo
    def first_dt(item: Dict[str, Any]) -> datetime:
        dates = item.get("seances") or []
        if not dates:
            return datetime.max
        try:
            return min(datetime.fromisoformat(d) for d in dates)
        except Exception:
            return datetime.max

    items.sort(key=first_dt)

    label = f"{year}-S{week:02d}"
    return {
        "week": label,
        "year": year,
        "weekNumber": week,
        "films": items,
    }


def list_weeks_sorted(desc: bool = False) -> List[Path]:
    files = [p for p in SEANCES_DIR.glob("*.json") if WEEK_FILE_PATTERN.match(p.name)]
    files.sort(key=lambda p: parse_week_from_filename(p.name), reverse=desc)
    return files


@app.route("/api/seances")
def api_seances():
    weeks = list_weeks_sorted(desc=False)
    payload = [build_week_payload(p) for p in weeks]
    # Ordonner: semaine courante d'abord, puis suivantes
    now = datetime.now()
    current_year, current_week, _ = now.isocalendar()

    def week_sort_key(w: Dict[str, Any]) -> tuple[int, int]:
        # Prioriser semaine >= courante; garder l'ordre croissant
        year = w["year"]
        week = w["weekNumber"]
        is_future_or_curr = (year, week) >= (current_year, current_week)
        return (0 if is_future_or_curr else 1, year, week)

    payload.sort(key=week_sort_key)
    # Ne garder que semaine courante et suivantes
    payload = [w for w in payload if (w["year"], w["weekNumber"]) >= (current_year, current_week)]
    return jsonify(payload)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    os.makedirs(STATIC_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)



