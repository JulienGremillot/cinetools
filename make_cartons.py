#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import glob
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Chemins
PATH_VIDEOS = 'bandes_annonces'
PATH_POSTERS = 'posters'
PATH_CARTONS = 'cartons'
PATH_RESOURCES = 'resources'

# Paramètres globaux
CARTON_MARGIN = 20
DATES = [
    ['Samedi 10 mai', '20h30'],
    ['Dimanche 11 mai', '17h00']
]

ADD_CARTON_CMD = (
    "ffmpeg -y -i \"{0}\" -loop 1 -t 5 -i \"{1}\" -f lavfi -t 5 -i anullsrc "
    "-filter_complex \"[0:v] [0:a] [1:v] [2:a] concat=n=2:v=1:a=1 [v] [a]\" "
    "-c:v libx264 -c:a aac -strict -2 -map \"[v]\" -map \"[a]\" \"{2}\""
)


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


def get_min_white_space(base_width, draw, font):
    max_width = 0
    for (jour, heure) in DATES:
        seance = '- ' + jour + ' à ' + heure
        bbox = draw.textbbox((0, 0), seance, font=font)
        width = bbox[2] - bbox[0]
        max_width = max(max_width, width)
    return base_width - max_width


def make_carton_for_video(video_path, poster_path, titre):
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

    font = ImageFont.truetype(font_path_regular, 35)
    line = 1
    if len(DATES) == 1:
        seance = DATES[0][0] + ' à ' + DATES[0][1]
        bbox = draw.textbbox((0, 0), seance, font=font)
        seance_width = bbox[2] - bbox[0]
        pos = (poster_img.width + CARTON_MARGIN * 3 + (width - poster_img.width - CARTON_MARGIN * 4 - seance_width) / 2,
               title_height + CARTON_MARGIN * 6 * line)
        draw.text(pos, seance, 'rgb(10,10,10)', font)
    else:
        white_space = get_min_white_space(width - poster_img.width - CARTON_MARGIN * 4, draw, font)
        coef_vertical = 3 if len(DATES) > 4 else 4
        for (date, heure) in DATES:
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


def process_all_videos():
    from datetime import datetime, timedelta

    processed = False
    date_obj = datetime.today()
    semaine_dir, videos_dir = get_videos_dir_from_date(date_obj)

    # On s'arrête dès qu'un sous-répertoire attendu n'existe pas
    while os.path.isdir(videos_dir):
        video_files = glob.glob(os.path.join(videos_dir, '*.mp4'))

        for video_path in video_files:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            poster_path = os.path.join(PATH_POSTERS, semaine_dir, base_name + '.jpg')

            if not os.path.exists(poster_path):
                print(f"[!] Poster manquant pour : {base_name} (semaine {semaine_dir}), vidéo ignorée.")
                continue

            make_carton_for_video(video_path, poster_path, base_name)
            processed = True

        # Incrémenter d'une semaine
        date_obj += timedelta(weeks=1)
        semaine_dir, videos_dir = get_videos_dir_from_date(date_obj)

    if not processed:
        print("Aucune vidéo traitée.")


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

    # Seuil de confiance: ajustable selon vos données (0.55 marche bien en général)
    return best_path if best_path and best_score >= 0.55 else None


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
            # On s'arrête dès qu'un sous-répertoire attendu n'existe pas
            break

        video_files = glob.glob(os.path.join(videos_dir, "*.mp4"))

        for video_path in video_files:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            poster_path = find_best_poster_path(semaine_dir, base_name)

            if not poster_path:
                print(f"[!] Poster manquant pour : {base_name} (semaine {semaine_dir}), vidéo ignorée.")
                continue

            print(f"[OK] Poster associé: {base_name} -> {os.path.basename(poster_path)} (semaine {semaine_dir})")
            make_carton_for_video(video_path, poster_path, base_name)
            processed = True

        # Incrémenter d'une semaine
        date_obj += timedelta(weeks=1)

    if not processed:
        print("Aucune vidéo trouvée.")


if __name__ == '__main__':
    process_all_videos()