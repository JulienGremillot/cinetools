import os
import json
from datetime import datetime, timedelta
from isoweek import Week
from dotenv import load_dotenv
import google.auth.transport.requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Scopes nécessaires (upload de vidéos)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def get_authenticated_service():
    flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
    creds = flow.run_local_server(port=0)
    return build("youtube", "v3", credentials=creds)

def get_playlist_name_from_seance_file(filepath):
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

    # Ajoute le mois si les mois sont différents ou l'année si les années sont différentes
    if wednesday.month != next_tuesday.month:
        end_date_str = next_tuesday.strftime(end_date_format)
        if wednesday.year != next_tuesday.year:
            start_date_str = wednesday.strftime("%d %B %Y")
        else:
            start_date_str = wednesday.strftime(start_date_format)
    elif wednesday.year != next_tuesday.year:
        start_date_str = wednesday.strftime("%d %B %Y")
        end_date_str = next_tuesday.strftime("%d %B %Y")
    else:
        start_date_str = wednesday.strftime(start_date_format)
        end_date_str = next_tuesday.strftime("%d %B %Y") # Always include year for the end date

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
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category
        },
        "status": {
            "privacyStatus": privacy
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
                    title = item.get("title", os.path.basename(video_file))
                    description = item.get("description", "")
                    category = item.get("category", "22")
                    privacy = item.get("privacy", "unlisted")

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
                        if "quotaExceeded" in str(e):
                            print("Quota YouTube dépassé. Arrêt des uploads.")
                            quota_error_occurred = True

            if updated_data:
                f.seek(0)
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.truncate()
                print(f"Fichier {filepath} mis à jour.")
    print("Processus d'upload terminé.")


if __name__ == "__main__":
    main()
