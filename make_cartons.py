#! /usr/bin/env python
# -*- coding: utf-8 -*-
# ... imports existants ...
import os
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import locale

# Chemins
PATH_VIDEOS = 'bandes_annonces'
PATH_POSTERS = 'posters'
PATH_CARTONS = 'cartons'
PATH_RESOURCES = 'resources'

# Paramètres globaux
CARTON_MARGIN = 20

ADD_CARTON_CMD = (
    "ffmpeg -y -i \"{0}\" -loop 1 -t 5 -i \"{1}\" -f lavfi -t 5 -i anullsrc "
    "-filter_complex \"[0:v] [0:a] [1:v] [2:a] concat=n=2:v=1:a=1 [v] [a]\" "
    "-c:v libx264 -c:a aac -strict -2 -map \"[v]\" -map \"[a]\" \"{2}\""
)

# Mettre la locale en français (si disponible sur ton système)
try:
    locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")  # Linux/macOS
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, "French_France")  # Windows
    except locale.Error:
        pass  # fallback si pas de locale FR installée

# --- fonctions existantes ---

def clean_title(titre):
    return titre.replace("'", " ").replace("?", "").replace(":", "-").replace("\n", " ")


def get_title_splitted_if_necessary(titre, draw, img_width, poster_width, font):
    bbox = draw.textbbox((0, 0), titre, font=font)
    title_width = bbox[2] - bbox[0]
    white_space = img_width - poster_width - CARTON_MARGIN * 4 - title_width
    if white_space < 0:
        mid = len(titre) // 2
        space_left = titre.rfind(' ', 0, mid)
        space_right = titre.find(' ', mid)
        if space_left > 0 or space_right > 0:
            split_pos = space_right if (len(titre) - space_right < space_left) else space_left
            titre = titre[:split_pos] + "\n" + titre[split_pos + 1:]
    return titre


def get_min_white_space(dates, base_width, draw, font):
    max_width = 0
    for (jour, heure) in dates:
        seance = '- ' + jour + ' à ' + heure
        bbox = draw.textbbox((0, 0), seance, font=font)
        width = bbox[2] - bbox[0]
        max_width = max(max_width, width)
    return base_width - max_width


def make_carton_for_video(video_path, poster_path, titre, dates_str):
    print(f"Traitement de : {video_path}")

    vid = cv2.VideoCapture(video_path)
    height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))

    carton = np.full((height, width, 3), 255, dtype=np.uint8)
    carton = Image.fromarray(carton)

    poster_img = Image.open(poster_path)
    poster_img.thumbnail((width - CARTON_MARGIN * 2, height - CARTON_MARGIN * 2))
    carton.paste(poster_img, (CARTON_MARGIN, CARTON_MARGIN))

    logo = Image.open(os.path.join(PATH_RESOURCES, 'logo.jpg'))
    carton.paste(logo, (width - CARTON_MARGIN - logo.width, height - CARTON_MARGIN - logo.height))

    font_size = 75
    font_path_bold = os.path.join(PATH_RESOURCES, 'Roboto-Bold.ttf')
    font_path_regular = os.path.join(PATH_RESOURCES, 'Roboto-Regular.ttf')
    font = ImageFont.truetype(font_path_bold, font_size)
    draw = ImageDraw.Draw(carton)

    titre = get_title_splitted_if_necessary(titre, draw, width, poster_img.width, font)
    bbox = draw.textbbox((0, 0), titre, font=font)
    title_width = bbox[2] - bbox[0]
    title_height = bbox[3] - bbox[1]
    white_space = (width - poster_img.width - CARTON_MARGIN * 4 - title_width)

    while white_space < 0 and font_size > 30:
        font_size -= 5
        font = ImageFont.truetype(font_path_bold, font_size)
        bbox = draw.textbbox((0, 0), titre, font=font)
        title_width = bbox[2] - bbox[0]
        title_height = bbox[3] - bbox[1]
        white_space = (width - poster_img.width - CARTON_MARGIN * 4 - title_width)

    pos = (poster_img.width + CARTON_MARGIN * 3 + white_space / 2, CARTON_MARGIN * 2)
    draw.text(pos, titre, 'rgb(10,10,10)', font)

    dates = []
    for date_string in dates_str:
        dt = datetime.fromisoformat(date_string)
        # Format : "Samedi 5 octobre"
        # jour sans zéro : %d donne 05 → on peut convertir en int
        jour_str = str(int(dt.strftime("%d")))
        date_str = dt.strftime("%A %B").capitalize()
        jour = f"{date_str.split()[0]} {jour_str} {date_str.split()[1]}"
        # Format heure : "20h30"
        heure = dt.strftime('%Hh%M')
        dates.append([jour, heure])

    font = ImageFont.truetype(font_path_regular, 35)
    line = 1
    if len(dates) == 1:
        seance = dates[0][0] + ' à ' + dates[0][1]
        bbox = draw.textbbox((0, 0), seance, font=font)
        seance_width = bbox[2] - bbox[0]
        pos = (poster_img.width + CARTON_MARGIN * 3 + (width - poster_img.width - CARTON_MARGIN * 4 - seance_width) / 2,
               title_height + CARTON_MARGIN * 6 * line)
        draw.text(pos, seance, 'rgb(10,10,10)', font)
    else:
        white_space = get_min_white_space(dates, width - poster_img.width - CARTON_MARGIN * 4, draw, font)
        coef_vertical = 3 if len(dates) > 4 else 4
        for (date, heure) in dates:
            pos = (
                poster_img.width + CARTON_MARGIN * 3 + white_space / 2,
                title_height + CARTON_MARGIN * 2 + CARTON_MARGIN * coef_vertical * line
            )
            draw.text(pos, f'- {date} à {heure}', 'rgb(10,10,10)', font)
            line += 1

    if not os.path.exists(PATH_CARTONS):
        os.makedirs(PATH_CARTONS)
    base_name = clean_title(titre)
    carton_file = os.path.join(PATH_CARTONS, base_name + '.png')
    carton.save(carton_file)

    output_video = video_path.replace('.mp4', '_new.mp4')
    cmd = ADD_CARTON_CMD.format(video_path, carton_file, output_video)
    print("Commande ffmpeg :", cmd)


def get_videos_dir_from_date(date_obj):
    annee = date_obj.strftime("%Y")
    num_semaine = date_obj.strftime("%V")
    semaine_dir = f"{annee}-S{num_semaine}"
    videos_dir = os.path.join(PATH_VIDEOS, semaine_dir)
    return semaine_dir, videos_dir


def _strip_accents(text: str) -> str:
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


def _normalize_title(text: str) -> str:
    import os
    import re
    if not text:
        return ""
    # Retirer extension éventuelle et remplacer les underscores
    text = os.path.splitext(text)[0].replace("_", " ")
    # Retirer les contenus entre parenthèses (souvent des mentions annexes)
    text = re.sub(r"\(.*?\)", " ", text)
    # Minuscules et suppression des accents
    text = _strip_accents(text.lower())
    # Garder que lettres/chiffres/espaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Espaces normalisés
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _score_similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    a = a.strip()
    b = b.strip()
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b).ratio()
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    jaccard = (len(tokens_a & tokens_b) / len(tokens_a | tokens_b)) if (tokens_a or tokens_b) else 0.0
    # Pondération: séquence 60% + Jaccard 40%
    return 0.6 * ratio + 0.4 * jaccard


def find_best_poster_path(semaine_dir: str, video_base_name: str):
    import os
    import glob
    posters_dir = os.path.join(PATH_POSTERS, semaine_dir)
    if not os.path.isdir(posters_dir):
        return None

    candidates = glob.glob(os.path.join(posters_dir, "*.jpg"))
    if not candidates:
        return None

    target_norm = _normalize_title(video_base_name)
    best_path = None
    best_score = 0.0
    for poster_path in candidates:
        poster_name = os.path.splitext(os.path.basename(poster_path))[0]
        poster_norm = _normalize_title(poster_name)
        score = _score_similarity(target_norm, poster_norm)
        if score > best_score:
            best_score = score
            best_path = poster_path

    return best_path if best_path and best_score >= 0.55 else None


# --- récupérer le titre et les dates depuis le fichier de séance en fonction du poster ---

def _get_title_from_seance_by_poster(semaine_dir: str, poster_path: str):
    """
    Ouvre seances/<semaine_dir>.json, cherche l'objet dont l'attribut 'file_poster'
    correspond au nom du poster (avec ou sans extension, insensible à la casse),
    et renvoie son titre (champs acceptés: 'title', 'titre', 'name', 'nom').
    Retourne None si non trouvé ou si le fichier n'existe pas.
    """
    import json

    seance_file = os.path.join('seances', f'{semaine_dir}.json')
    if not os.path.isfile(seance_file):
        return None

    try:
        with open(seance_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[!] Impossible de lire {seance_file}: {e}")
        return None

    def norm_filename(name: str) -> str:
        return os.path.splitext(os.path.basename(str(name)))[0].lower().strip()

    target = norm_filename(poster_path)

    def iter_items(d):
        if isinstance(d, list):
            for it in d:
                yield it
        elif isinstance(d, dict):
            # Listes possibles dans différents champs
            for key in ('films', 'seances', 'items', 'programme', 'program'):
                lst = d.get(key)
                if isinstance(lst, list):
                    for it in lst:
                        yield it
            # Cas dict d'objets
            for v in d.values():
                if isinstance(v, dict) and any(k in v for k in ('file_poster', 'title', 'titre')):
                    yield v

    for item in iter_items(data):
        if not isinstance(item, dict):
            continue
        poster_candidate = (
            item.get('file_poster') or
            item.get('poster_file') or
            item.get('poster') or
            item.get('filePoster')
        )
        if not poster_candidate:
            continue
        if norm_filename(poster_candidate) != target:
            continue

        for title_key in ('title', 'titre', 'name', 'nom'):
            title_val = item.get(title_key)
            if isinstance(title_val, str) and title_val.strip():
                return title_val.strip(), item.get('seances')

    return None


# --- process_all_videos: utilise maintenant le titre du fichier de séance comme base_name ---

# -----------------------------------------------------------
# Nouveau: mise à jour du fichier seances/<semaine_dir>.json
# -----------------------------------------------------------

def _update_seances_json(semaine_dir: str, updates: list[dict]) -> None:
    """
    Met à jour seances/<semaine_dir>.json en ajoutant pour chaque film
    les champs 'file_bandeannonce' et 'file_carton'.

    Paramètres:
      - semaine_dir: ex. "2025-S35"
      - updates: liste de dicts du type:
          {
            "titre": "<Titre séance>",
            "file_bandeannonce": "<chemin absolu vers la BA utilisée>",
            "file_carton": "<chemin absolu vers le carton .png généré>"
          }
    """
    json_path = Path("seances") / f"{semaine_dir}.json"
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                print(f"[WARN] Contenu inattendu dans {json_path}, remplacement par une liste.")
                data = []
    except FileNotFoundError:
        print(f"[WARN] Fichier non trouvé: {json_path}. Création d'un nouveau.")
        data = []

    # Indexer par titre pour mise à jour rapide
    by_title: dict[str, dict] = {}
    order: list[str] = []
    for item in data:
        if isinstance(item, dict):
            t = item.get("titre")
            if t is not None:
                by_title[t] = item
                order.append(t)

    # Appliquer les mises à jour
    for upd in updates:
        titre = upd["titre"]
        ba = upd["file_bandeannonce"]
        carton = upd["file_carton"]
        if titre in by_title:
            by_title[titre]["file_bandeannonce"] = ba
            by_title[titre]["file_carton"] = carton
        else:
            # Titre absent: on l'ajoute avec un minimum d'infos
            by_title[titre] = {
                "titre": titre,
                "seances": [],
                "file_bandeannonce": ba,
                "file_carton": carton,
            }
            order.append(titre)

    # Reconstruire la liste dans l'ordre d'origine + nouveaux à la fin
    new_list = [by_title[t] for t in order]

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(new_list, f, ensure_ascii=False, indent=2)
    print(f"[OK] Mise à jour des chemins dans {json_path}")

# ----------------------------------------------------------------
# Dans votre logique principale, pendant le traitement d’une semaine
# ----------------------------------------------------------------

def process_all_videos():
    from datetime import datetime, timedelta
    import os
    import glob

    processed = False
    date_obj = datetime.today()

    while True:
        annee = date_obj.strftime("%Y")
        num_semaine = date_obj.strftime("%V")
        semaine_dir = f"{annee}-S{num_semaine}"

        videos_dir = os.path.join(PATH_VIDEOS, semaine_dir)
        if not os.path.isdir(videos_dir):
            break

        video_files = glob.glob(os.path.join(videos_dir, "*.mp4"))

        # ... au début du traitement de la semaine, juste avant la boucle sur les BAs :
        updates_for_json: list[dict] = []

        for video_path in video_files:
            video_base_name = os.path.splitext(os.path.basename(video_path))[0]
            poster_path = find_best_poster_path(semaine_dir, video_base_name)

            if not poster_path:
                print(f"[!] Poster manquant pour : {video_base_name} (semaine {semaine_dir}), vidéo ignorée.")
                continue

            # Récupère le titre et les dates depuis seances/<semaine_dir>.json en se basant sur le fichier poster
            seance_title, dates = _get_title_from_seance_by_poster(semaine_dir, os.path.basename(poster_path))
            titre_final = seance_title if seance_title else video_base_name

            if seance_title:
                print(f"[OK] Poster associé: {video_base_name} -> {os.path.basename(poster_path)} ; titre séance: \"{seance_title}\"")
            else:
                print(f"[OK] Poster associé: {video_base_name} -> {os.path.basename(poster_path)} ; titre séance introuvable, on garde \"{video_base_name}\"")

            make_carton_for_video(video_path, poster_path, titre_final, dates)
            processed = True

            # ... dans la boucle où vous traitez chaque bande-annonce et générez le carton:
            # Supposons que vous disposiez déjà de:
            # - semaine_dir: str (ex. "2025-S35")
            # - seance_title: str (le titre exact de la séance)
            # - ba_input_path: str ou Path (chemin vers la bande-annonce en entrée)
            # - carton_png_path: str ou Path (chemin du .png généré pour ce film)

            # Après avoir déterminé ces chemins et généré le carton, ajoutez:
            carton_png_path = os.path.join(PATH_CARTONS, clean_title(titre_final) + '.png')  # deduit le chemin du carton
            updates_for_json.append({
                "titre": seance_title,
                "file_bandeannonce": str(Path(video_path).resolve()),
                "file_carton": str(Path(carton_png_path).resolve()),
            })

        # ... après avoir terminé la boucle de traitement de toutes les BAs de la semaine :
        _update_seances_json(semaine_dir, updates_for_json)

        date_obj += timedelta(weeks=1)

    if not processed:
        print("Aucune vidéo trouvée.")


if __name__ == '__main__':
    process_all_videos()