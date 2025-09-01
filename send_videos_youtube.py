import os
import json
from datetime import datetime
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
