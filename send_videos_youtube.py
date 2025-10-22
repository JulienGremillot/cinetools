import os
import json
from datetime import datetime, timedelta
from isoweek import Week
import locale
from dotenv import load_dotenv
import google.auth.transport.requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import unicodedata
import re
import html as html_lib

# Scopes nécessaires (upload de vidéos)
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def _is_allowed_char_for_youtube(ch: str) -> bool:
    """Filtre les caractères problématiques pour les champs texte YouTube.
    - Autorise les retours à la ligne (\n)
    - Supprime les caractères de contrôle (catégorie Unicode Cc) et les surrogates (Cs)
    - Supprime les non-caractères Unicode (U+FDD0..U+FDEF, U+xxFFFE, U+xxFFFF)
    """
    if ch == "\n":
        return True
    cp = ord(ch)
    cat = unicodedata.category(ch)
    # Contrôle, Surrogates, Format, Private-use -> retirer
    if cat in ("Cc", "Cs", "Cf", "Co"):
        return False
    if 0xFDD0 <= cp <= 0xFDEF:
        return False
    if (cp & 0xFFFF) in (0xFFFE, 0xFFFF):
        return False
    return True

def _strip_html(text: str) -> str:
    # Supprime les balises HTML rudimentaires
    return re.sub(r"<[^>]+>", " ", text)

def sanitize_youtube_text(text: str | None, max_length: int) -> str:
    """Normalise, nettoie et tronque un texte pour l'API YouTube.
    - Normalisation NFKC
    - Uniformisation des sauts de ligne en \n
    - Suppression des chars de contrôle et non-caractères
    - Tronquage à max_length
    """
    if not text:
        return ""
    cleaned = unicodedata.normalize("NFKC", str(text))
    # Décodage des entités HTML (ex: &nbsp;)
    cleaned = html_lib.unescape(cleaned)
    # Suppression des balises HTML éventuelles
    cleaned = _strip_html(cleaned)
    # Normalisation des fins de ligne et séparateurs spéciaux
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\u2028", "\n").replace("\u2029", "\n")
    # Remplacer NBSP et espaces typographiques par un espace normal
    cleaned = cleaned.replace("\u00A0", " ")
    cleaned = re.sub("[\u2000-\u200B\u202F\u205F\u3000]", " ", cleaned)
    cleaned = "".join(ch for ch in cleaned if _is_allowed_char_for_youtube(ch))
    # Réduction des espaces (conserve les \n)
    cleaned = re.sub(r"[\t\f\v ]+", " ", cleaned)
    # Nettoyage des espaces autour des sauts de ligne
    cleaned = re.sub(r" *\n+ *", "\n", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned

def get_authenticated_service():
    flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
    creds = flow.run_local_server(port=0)
    return build("youtube", "v3", credentials=creds)

def get_playlist_name_from_seance_file(filepath):
    # Définir le locale en français pour le formatage des dates
    locale.setlocale(locale.LC_TIME, 'fr_FR.utf8') # Pour Linux/macOS
    # Pour Windows, vous pourriez avoir besoin de 'fra_FRA' ou 'French_France.1252'
    # locale.setlocale(locale.LC_ALL, 'French_France.1252') 

    # Extrait l'année et le numéro de semaine du nom de fichier (ex: 2025-S36.json)
    filename = os.path.basename(filepath)
    year_str, week_str = filename.split('-S')
    year = int(year_str)
    week_number = int(week_str.split('.')[0])

    # Crée un objet Week
    current_week = Week(year, week_number)

    # Calcule le mercredi de la semaine (jour 3 de la semaine ISO)
    wednesday = current_week.day(2) # Monday is 0, Tuesday is 1, Wednesday is 2

    # Calcule le mardi de la semaine suivante
    next_week = current_week + 1
    next_tuesday = next_week.day(1) # Tuesday is 1

    # Formate les dates
    start_date_format = "%d %B"
    end_date_format = "%d %B %Y"

    # Formater les jours sans zéro non significatif
    start_day = str(wednesday.day)
    end_day = str(next_tuesday.day)

    # Gérer la répétition du mois et de l'année
    if wednesday.year != next_tuesday.year:
        start_date_str = wednesday.strftime(f"%#d %B %Y" if os.name == 'nt' else f"%-d %B %Y")
        end_date_str = next_tuesday.strftime(f"%#d %B %Y" if os.name == 'nt' else f"%-d %B %Y")
    elif wednesday.month != next_tuesday.month:
        start_date_str = wednesday.strftime(f"%#d %B" if os.name == 'nt' else f"%-d %B")
        end_date_str = next_tuesday.strftime(f"%#d %B %Y" if os.name == 'nt' else f"%-d %B %Y")
    else:
        # Même mois et même année, ne pas répéter le mois pour la date de début
        start_date_str = wednesday.strftime(f"%#d" if os.name == 'nt' else f"%-d")
        end_date_str = next_tuesday.strftime(f"%#d %B %Y" if os.name == 'nt' else f"%-d %B %Y")

    return f"Semaine du {start_date_str} au {end_date_str}"

def get_or_create_playlist(youtube_service, title, description="", privacy_status="unlisted"):
    # Vérifier si la playlist existe déjà
    response = youtube_service.playlists().list(
        part="snippet",
        mine=True,
        maxResults=50
    ).execute()

    for item in response["items"]:
        if item["snippet"]["title"] == title:
            print(f"Playlist \"{title}\" trouvée avec l'ID : {item['id']}")
            return item["id"]

    # Si la playlist n'existe pas, la créer
    request_body = {
        "snippet": {
            "title": title,
            "description": description
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }
    response = youtube_service.playlists().insert(
        part="snippet,status",
        body=request_body
    ).execute()
    print(f"Playlist \"{title}\" créée avec l'ID : {response['id']}")
    return response["id"]

def add_video_to_playlist(youtube_service, playlist_id, video_id):
    request_body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id
            }
        }
    }
    response = youtube_service.playlistItems().insert(
        part="snippet",
        body=request_body
    ).execute()
    print(f"Vidéo {video_id} ajoutée à la playlist {playlist_id}.")
    return response

def get_seance_files(base_dir="./seances"):
    seance_files = []
    today = datetime.now()
    current_week = Week.withdate(today)

    while True:
        year = current_week.year
        week_number = current_week.week
        filename = os.path.join(base_dir, f"{year}-S{week_number:02d}.json")

        if os.path.exists(filename):
            seance_files.append(filename)
            current_week += 1  # Passe à la semaine suivante
        else:
            break  # Arrête quand il n'y a plus de fichier

    return seance_files

def upload_video(youtube, file, title, description, category="22", privacy="public"):
    # Sécuriser titre/description pour éviter invalidDescription/invalidTitle
    safe_title = sanitize_youtube_text(title, 100)
    if not safe_title:
        safe_title = os.path.basename(file)
    safe_description = sanitize_youtube_text(description, 5000)

    # Logs concis pour diagnostic
    preview_title = (safe_title[:120] + ("..." if len(safe_title) > 120 else ""))
    print(f"Titre (len={len(safe_title)}): {preview_title}")
    print(f"Description (len={len(safe_description)})")

    request_body = {
        "snippet": {
            "title": safe_title,
            "description": safe_description,
            "categoryId": category
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False  # Précise que la vidéo n'est pas conçue pour les enfants
        }
    }

    media_file = MediaFileUpload(file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media_file
    )

    response = request.execute()
    print(f"Vidéo envoyée : https://youtu.be/{response['id']}")
    return f"https://youtu.be/{response['id']}"


def main():
    seance_files = get_seance_files()
    youtube_service = get_authenticated_service()
    quota_error_occurred = False

    for filepath in seance_files:
        if quota_error_occurred:
            break

        playlist_title = get_playlist_name_from_seance_file(filepath)
        playlist_id = get_or_create_playlist(youtube_service, playlist_title)

        with open(filepath, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            updated_data = False

            for item in data:
                if quota_error_occurred:
                    break

                if "file_youtube" in item and "url_youtube" not in item:
                    video_file = item["file_youtube"]
                    title = item.get("titre", os.path.basename(video_file))  # Utilise l'attribut "titre"
                    description = item.get("description", "")  # Utilise l'attribut "description"
                    category = item.get("category", "22")
                    privacy = "public" # Force la confidentialité à "public"

                    if not os.path.exists(video_file):
                        print(f"Fichier vidéo non trouvé : {video_file}")
                        continue

                    try:
                        print(f"Tentative d'upload de {video_file}...")
                        youtube_url = upload_video(youtube_service, video_file, title, description, category, privacy)
                        item["url_youtube"] = youtube_url
                        
                        # Extraire l'ID de la vidéo de l'URL YouTube
                        video_id = youtube_url.split('/')[-1]
                        if playlist_id:
                            add_video_to_playlist(youtube_service, playlist_id, video_id)

                        updated_data = True
                    except Exception as e:
                        print(f"Erreur lors de l'upload de {video_file}: {e}")
                        # Mise à jour pour détecter le message spécifique de l'erreur de quota
                        if "The user has exceeded the number of videos they may upload" in str(e):
                            print("Quota YouTube dépassé. Arrêt des uploads.")
                            quota_error_occurred = True
                        if "invalidDescription" in str(e):
                            # Informations de débogage additionnelles
                            print(f"[DEBUG] Description invalide détectée. Longueur après nettoyage: {len(sanitize_youtube_text(description, 5000))}")

            if updated_data:
                f.seek(0)
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.truncate()
                print(f"Fichier {filepath} mis à jour.")
    print("Processus d'upload terminé.")


if __name__ == "__main__":
    main()
