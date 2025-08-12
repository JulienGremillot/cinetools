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
    video_files = glob.glob(os.path.join(PATH_VIDEOS, '*.mp4'))

    if not video_files:
        print("Aucune vidéo trouvée.")
        return

    for video_path in video_files:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        poster_path = os.path.join(PATH_POSTERS, base_name + '.jpg')

        if not os.path.exists(poster_path):
            print(f"[!] Poster manquant pour : {base_name}, vidéo ignorée.")
            continue

        make_carton_for_video(video_path, poster_path, base_name)


if __name__ == '__main__':
    process_all_videos()
