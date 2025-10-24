import argparse
import os
from datetime import datetime, timedelta
import glob

import yt_dlp
from dotenv import load_dotenv
from googleapiclient.discovery import build


# Exemple d'utilisation :
# python get_bandes_annonces.py --channels config/channels.txt --output bandes_annonces/2025-S28

# --------- PRE-REQUIS ------------
# pip install google-api-python-client yt-dlp
# pip install python-dotenv
# ---------------------------------

# --------- CONFIGURATION ---------
CHANNELS = "config/channels.txt"
DOWNLOAD_PATH = "bandes_annonces"
MAX_RESULTS = 5
# ---------------------------------

# Charger les variables d'environnement
load_dotenv()

# Lire la clé depuis le fichier .env
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # clé API YouTube

if not YOUTUBE_API_KEY:
    raise RuntimeError("Clé API YouTube manquante. Vérifiez votre fichier .env.")


def search_trailer(title, allowed_channels=None):
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    query = f"{title} bande annonce"
    request = youtube.search().list(
        part="snippet",
        q=query,
        type="video",
        maxResults=MAX_RESULTS,
        videoEmbeddable="true"
    )
    response = request.execute()

    for item in response["items"]:
        channel = item["snippet"]["channelTitle"]
        print(f"[?] Bande-annonce éventuelle : {title} ({channel})")
        video_id = item["id"]["videoId"]
        if not allowed_channels or channel in allowed_channels:
            print(f"[✓] Bande-annonce trouvée : {title} ({channel})")
            return f"https://www.youtube.com/watch?v={video_id}"

    print(f"[✗] Aucune bande-annonce trouvée pour : {title}")
    return None


def download_video(url, title, output_path, cookies_file=None, browser_cookies=None):
    os.makedirs(output_path, exist_ok=True)
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": os.path.join(output_path, f"{title}.%(ext)s"),
        "quiet": False,
        "merge_output_format": "mp4",
        # Configuration pour éviter la détection de bot
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "referer": "https://www.youtube.com/",
        "sleep_interval": 1,  # Délai entre les requêtes
        "max_sleep_interval": 5,
        # Options pour contourner les restrictions
        "extractor_retries": 3,
        "fragment_retries": 3,
        "retries": 3,
        "no_check_certificate": True,
    }
    
    # Ajouter les cookies si fournis
    if cookies_file and os.path.exists(cookies_file):
        ydl_opts["cookiefile"] = cookies_file
        print(f"[!] Utilisation du fichier cookies: {cookies_file}")
    elif browser_cookies:
        ydl_opts["cookiesfrombrowser"] = (browser_cookies, None, None, None)
        print(f"[!] Utilisation des cookies du navigateur: {browser_cookies}")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        print(f"[✗] Erreur lors du téléchargement de {title}: {e}")
        print("[!] Essayez d'utiliser --cookies-from-browser chrome ou --cookies cookies.txt")
        return False
    return True


def load_titles(path):
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    else:
        return []


def load_titles_for_date(date_obj):
    annee = date_obj.strftime("%Y")
    num_semaine = date_obj.strftime("%V")
    return load_titles(f"films/{annee}-S{num_semaine}.txt")


def load_channels(path):
    if not path:
        print("Fichier des chaines Youtube non trouvé")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main(args):

    allowed_channels = load_channels(args.channels)

    # détermine les fichiers à parcourir : on commence par la semaine courante
    date_obj = datetime.now()

    titles = load_titles_for_date(date_obj)
    while len(titles) > 0:
        for title in titles:
            if args.output:
                output_path = args.output
            else:
                annee = date_obj.strftime("%Y")
                num_semaine = date_obj.strftime("%V")
                output_path = f"{DOWNLOAD_PATH}/{annee}-S{num_semaine}"
            bande_annonce = glob.glob(f"{output_path}/{title}.*")
            if bande_annonce:
                print(f"Bande-annonce de {title} déjà téléchargée.")
            else:
                url = search_trailer(title, allowed_channels)
                if url:
                    download_video(url, title, output_path, args.cookies, args.browser_cookies)

        # puis on passe à la semaine suivante
        date_obj += timedelta(weeks=1)
        titles = load_titles_for_date(date_obj)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Téléchargeur de bandes-annonces YouTube")
    parser.add_argument("--channels", default=CHANNELS,
                        help="Fichier texte contenant les noms de chaînes autorisées (1 par ligne)")
    parser.add_argument("--output", required=False, help="Dossier de téléchargement")
    parser.add_argument("--cookies", required=False, help="Fichier cookies pour l'authentification YouTube")
    parser.add_argument("--browser-cookies", required=False, 
                        choices=["chrome", "firefox", "safari", "edge"],
                        help="Utiliser les cookies du navigateur (chrome, firefox, safari, edge)")

    args = parser.parse_args()
    main(args)
