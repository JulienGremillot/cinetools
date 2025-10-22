
import os
import re
from pathlib import Path
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone
import dateutil.parser
from dateutil import tz

load_dotenv()

META_LONG_LIVED_TOKEN = os.getenv("META_LONG_LIVED_TOKEN") # Peut encore être utile pour d'autres opérations utilisateur si nécessaire
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")

def get_long_lived_page_token():
    """Convertit un token de courte durée en token de longue durée (60 jours)"""
    if not all([APP_ID, APP_SECRET, PAGE_ACCESS_TOKEN]):
        print("Erreur : APP_ID, APP_SECRET et PAGE_ACCESS_TOKEN doivent être configurés dans .env")
        return None
    
    # Étape 1 : Échanger le token utilisateur contre un token de longue durée
    url = "https://graph.facebook.com/v23.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": PAGE_ACCESS_TOKEN
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        long_lived_user_token = response.json().get("access_token")
        print(f"✓ Token utilisateur de longue durée obtenu")
        
        # Étape 2 : Obtenir le token de page (qui n'expire jamais tant que l'app existe)
        page_url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}"
        page_params = {
            "fields": "access_token",
            "access_token": long_lived_user_token
        }
        
        response = requests.get(page_url, params=page_params)
        response.raise_for_status()
        page_token = response.json().get("access_token")
        
        print(f"✓ Token de page obtenu (longue durée)")
        print(f"\nNouveau PAGE_ACCESS_TOKEN :\n{page_token}\n")
        print("Copiez ce token dans votre fichier .env")
        
        return page_token
        
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l'obtention du token de longue durée : {e}")
        try:
            print(f"Détails : {response.json()}")
        except:
            pass
        return None

def get_scheduled_posts():
    if not PAGE_ACCESS_TOKEN:
        print("Erreur : Le PAGE_ACCESS_TOKEN n'est pas configuré dans le fichier .env")
        return

    if not FACEBOOK_PAGE_ID:
        print("Erreur : L'ID de la page Facebook n'est pas configuré. Veuillez définir 'FACEBOOK_PAGE_ID' dans le fichier .env.")
        return

    # Vérifier que le token courant est bien un token de la Page configurée
    try:
        debug_me_url = "https://graph.facebook.com/v23.0/me"
        debug_me_params = {
            "access_token": PAGE_ACCESS_TOKEN,
            "fields": "id,name"
        }
        response = requests.get(debug_me_url, params=debug_me_params)
        response.raise_for_status()
        me_data = response.json()
        current_token_page_id = me_data.get("id")
        current_token_page_name = me_data.get("name")
        print(f"Token de Page pour: {current_token_page_name} (id={current_token_page_id})")
        if str(current_token_page_id) != str(FACEBOOK_PAGE_ID):
            print("Attention: l'ID de la Page du token ne correspond pas à FACEBOOK_PAGE_ID du .env")
    except requests.exceptions.RequestException:
        pass

    # Récupérer l'ID du compte Instagram Business lié à la page Facebook
    instagram_business_account_id = None
    page_info_url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}"
    page_info_params = {
        "access_token": PAGE_ACCESS_TOKEN, # Utilisation du PAGE_ACCESS_TOKEN ici
        "fields": "instagram_business_account"
    }
    try:
        response = requests.get(page_info_url, params=page_info_params)
        response.raise_for_status()
        page_info = response.json()
        if "instagram_business_account" in page_info:
            instagram_business_account_id = page_info["instagram_business_account"]["id"]
            print(f"ID du compte Instagram Business : {instagram_business_account_id}")
        else:
            print("Aucun compte Instagram Business trouvé pour cette page Facebook.")
            # On peut continuer sans l'ID Instagram si ce n'est pas critique pour le reste du script
            instagram_business_account_id = None 
            
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération de l'ID du compte Instagram Business : {e}")
        # Afficher plus de détails sur l'erreur
        try:
            error_details = response.json()
            print(f"Détails de l'erreur : {error_details}")
        except:
            print(f"Contenu de la réponse : {response.text if 'response' in locals() else 'Non disponible'}")
        instagram_business_account_id = None # S'assurer que la variable est définie même en cas d'erreur

    # Pour Facebook posts programmés
    # doc: https://developers.facebook.com/docs/graph-api/reference/page/scheduled_posts/
    facebook_url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/scheduled_posts"
    params = {
        "access_token": PAGE_ACCESS_TOKEN, # Utilisation du PAGE_ACCESS_TOKEN ici
        "fields": "id,message,created_time,scheduled_publish_time,is_published",
        "limit": 100
    }
    
    try:
        response = requests.get(facebook_url, params=params)
        response.raise_for_status() # Lève une exception pour les codes d'état HTTP d'erreur
        scheduled_posts = response.json()
        print("--- Publications Facebook programmées ---")
        if scheduled_posts and "data" in scheduled_posts:
            for post in scheduled_posts["data"]:
                print(f"ID: {post.get('id')}")
                print(f"Message: {post.get('message')}")
                print(f"Temps de création: {post.get('created_time')}")
                print(f"Temps de publication programmé: {post.get('scheduled_publish_time')}")
                print(f"Est publié: {post.get('is_published')}")
                print("-" * 20)
        else:
            print("Aucune publication Facebook programmée trouvée.")

            # Fallback: tenter via l'edge promotable_posts (inclut les posts non publiés / schedulés)
            try:
                promotable_url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/promotable_posts"
                promotable_params = {
                    "access_token": PAGE_ACCESS_TOKEN,
                    "fields": "id,message,created_time,is_published,scheduled_publish_time,status_type,permalink_url",
                    "limit": 100
                }
                response = requests.get(promotable_url, params=promotable_params)
                response.raise_for_status()
                promotable_posts = response.json()

                print("--- Vérification via promotable_posts (fallback) ---")
                found_any = False
                if promotable_posts and "data" in promotable_posts:
                    for post in promotable_posts["data"]:
                        # Considérer comme potentiellement programmé si non publié + scheduled_publish_time présent
                        if not post.get("is_published") and post.get("scheduled_publish_time") is not None:
                            found_any = True
                            print(f"ID: {post.get('id')}")
                            print(f"Message: {post.get('message')}")
                            print(f"Temps de création: {post.get('created_time')}")
                            print(f"Temps de publication programmé: {post.get('scheduled_publish_time')}")
                            print(f"Est publié: {post.get('is_published')}")
                            print(f"Type: {post.get('status_type')}")
                            print(f"Permalink: {post.get('permalink_url')}")
                            print("-" * 20)

                if not found_any:
                    print("Aucun post potentiellement programmé trouvé via promotable_posts.")

                # Deuxième fallback: unpublished_posts (contient brouillons, programmés, non publiés)
                try:
                    unpublished_url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/unpublished_posts"
                    unpublished_params = {
                        "access_token": PAGE_ACCESS_TOKEN,
                        "fields": "id,message,created_time,is_published,scheduled_publish_time,status_type,permalink_url",
                        "limit": 100
                    }
                    response = requests.get(unpublished_url, params=unpublished_params)
                    response.raise_for_status()
                    unpublished_posts = response.json()

                    print("--- Vérification via unpublished_posts (fallback) ---")
                    found_any_unpub = False
                    if unpublished_posts and "data" in unpublished_posts:
                        for post in unpublished_posts["data"]:
                            if not post.get("is_published") and post.get("scheduled_publish_time") is not None:
                                found_any_unpub = True
                                print(f"ID: {post.get('id')}")
                                print(f"Message: {post.get('message')}")
                                print(f"Temps de création: {post.get('created_time')}")
                                print(f"Temps de publication programmé: {post.get('scheduled_publish_time')}")
                                print(f"Est publié: {post.get('is_published')}")
                                print(f"Type: {post.get('status_type')}")
                                print(f"Permalink: {post.get('permalink_url')}")
                                print("-" * 20)

                    if not found_any_unpub:
                        print("Aucun post potentiellement programmé trouvé via unpublished_posts.")
                except requests.exceptions.RequestException as e_unpub:
                    print(f"Erreur lors de la vérification via unpublished_posts : {e_unpub}")
                    try:
                        print(f"Détails : {response.json()}")
                    except:
                        print(f"Contenu de la réponse : {response.text if 'response' in locals() else 'Non disponible'}")

                # Troisième fallback: vidéos programmées (posts vidéo/Reels planifiés)
                try:
                    videos_url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/videos"
                    videos_params = {
                        "access_token": PAGE_ACCESS_TOKEN,
                        "fields": "id,description,created_time,permalink_url,scheduled_publish_time,unpublished_content_type,status,length",
                        "limit": 100
                    }
                    response = requests.get(videos_url, params=videos_params)
                    response.raise_for_status()
                    videos = response.json()

                    print("--- Vérification des vidéos programmées (fallback) ---")
                    found_any_vid = False
                    if videos and "data" in videos:
                        for v in videos["data"]:
                            unpublished_type = v.get("unpublished_content_type")
                            scheduled_ts = v.get("scheduled_publish_time")
                            is_scheduled = (unpublished_type in ("SCHEDULED", "SCHEDULED_RECURRING")) or (scheduled_ts is not None)
                            if is_scheduled:
                                found_any_vid = True
                                print(f"ID: {v.get('id')}")
                                print(f"Description: {v.get('description')}")
                                print(f"Temps de création: {v.get('created_time')}")
                                print(f"Temps de publication programmé: {v.get('scheduled_publish_time')}")
                                print(f"Type non publié: {v.get('unpublished_content_type')}")
                                print(f"Statut: {v.get('status')}")
                                print(f"Permalink: {v.get('permalink_url')}")
                                print("-" * 20)

                    if not found_any_vid:
                        print("Aucune vidéo programmée trouvée via /videos.")
                except requests.exceptions.RequestException as e_v:
                    print(f"Erreur lors de la vérification des vidéos programmées : {e_v}")
                    try:
                        print(f"Détails : {response.json()}")
                    except:
                        print(f"Contenu de la réponse : {response.text if 'response' in locals() else 'Non disponible'}")

            except requests.exceptions.RequestException as e:
                print(f"Erreur lors de la vérification via promotable_posts : {e}")
                try:
                    print(f"Détails : {response.json()}")
                except:
                    print(f"Contenu de la réponse : {response.text if 'response' in locals() else 'Non disponible'}")

    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des publications Facebook programmées : {e}")
        # Afficher plus de détails sur l'erreur retournée par l'API Graph
        try:
            error_details = response.json()
            print(f"Détails de l'erreur : {error_details}")
        except:
            print(f"Contenu de la réponse : {response.text if 'response' in locals() else 'Non disponible'}")
    
    # Pour Instagram posts programmés
    # doc: https://developers.facebook.com/docs/instagram-api/reference/instagram-business-account/media#getting-scheduled-posts
    if instagram_business_account_id:
        instagram_url = f"https://graph.facebook.com/v23.0/{instagram_business_account_id}/media"
        instagram_params = {
            "access_token": PAGE_ACCESS_TOKEN, # Utilisation du PAGE_ACCESS_TOKEN ici
            "fields": "id,caption,media_type,timestamp,is_published,permalink"
        }

        try:
            response = requests.get(instagram_url, params=instagram_params)
            response.raise_for_status()
            instagram_media = response.json()
            
            print("\n--- Publications Instagram (à vérifier manuellement pour les posts programmés) ---")
            if instagram_media and "data" in instagram_media:
                found_scheduled = False
                for media in instagram_media["data"]:
                    media_timestamp = media.get('timestamp')
                    is_published = media.get('is_published')
                    
                    # Convertir le timestamp en objet datetime pour comparaison
                    current_time = datetime.now(dateutil.parser.parse(media_timestamp).tzinfo)

                    # Si le post n'est pas publié et que son timestamp est dans le futur
                    if not is_published and dateutil.parser.parse(media_timestamp) > current_time:
                        found_scheduled = True
                        print(f"ID: {media.get('id')}")
                        print(f"Caption: {media.get('caption', 'N/A')}")
                        print(f"Type de média: {media.get('media_type')}")
                        print(f"Timestamp: {media.get('timestamp')}")
                        print(f"Permalink: {media.get('permalink')}")
                        print(f"Est publié: {media.get('is_published')}")
                        print("-" * 20)
                
                if not found_scheduled:
                    print("Aucune publication Instagram 'programmée' potentielle trouvée (non publiée avec timestamp futur).")

            else:
                print("Aucun média Instagram trouvé pour ce compte.")

        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération des médias Instagram : {e}")
    else:
        print("Skipping Instagram scheduled posts check as no Instagram Business Account ID was found.")

def _collect_scheduled_timestamps() -> set:
    """Retourne l'ensemble des timestamps Unix UTC (int) des publications déjà programmées.
    Agrège les infos depuis plusieurs endpoints (scheduled_posts, promotable_posts, unpublished_posts, videos).
    """
    scheduled_timestamps: set[int] = set()

    if not PAGE_ACCESS_TOKEN or not FACEBOOK_PAGE_ID:
        return scheduled_timestamps

    # 1) scheduled_posts
    try:
        url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/scheduled_posts"
        params = {
            "access_token": PAGE_ACCESS_TOKEN,
            "fields": "scheduled_publish_time",
            "limit": 100,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        for post in data.get("data", []):
            ts = post.get("scheduled_publish_time")
            if isinstance(ts, int):
                scheduled_timestamps.add(ts)
            else:
                # Parfois renvoyé en str
                try:
                    scheduled_timestamps.add(int(ts))
                except Exception:
                    pass
    except Exception:
        pass

    # 2) promotable_posts (fallback)
    try:
        url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/promotable_posts"
        params = {
            "access_token": PAGE_ACCESS_TOKEN,
            "fields": "scheduled_publish_time,is_published",
            "limit": 100,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        for post in data.get("data", []):
            if post.get("is_published"):
                continue
            ts = post.get("scheduled_publish_time")
            if ts is None:
                continue
            try:
                scheduled_timestamps.add(int(ts))
            except Exception:
                pass
    except Exception:
        pass

    # 3) unpublished_posts (fallback)
    try:
        url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/unpublished_posts"
        params = {
            "access_token": PAGE_ACCESS_TOKEN,
            "fields": "scheduled_publish_time,is_published",
            "limit": 100,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        for post in data.get("data", []):
            if post.get("is_published"):
                continue
            ts = post.get("scheduled_publish_time")
            if ts is None:
                continue
            try:
                scheduled_timestamps.add(int(ts))
            except Exception:
                pass
    except Exception:
        pass

    # 4) videos programmées
    try:
        url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/videos"
        params = {
            "access_token": PAGE_ACCESS_TOKEN,
            "fields": "scheduled_publish_time,unpublished_content_type",
            "limit": 100,
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        for v in data.get("data", []):
            ts = v.get("scheduled_publish_time")
            if ts is None:
                continue
            try:
                scheduled_timestamps.add(int(ts))
            except Exception:
                pass
    except Exception:
        pass

    return scheduled_timestamps

# Nouveau format: YYYY-MM-DD-HHhMM-YYYY-SWW-<poster>.<ext>.txt
# Ancien format supporté en fallback: YYYY-MM-DD-HHhMM.txt
_POST_FILENAME_RE = re.compile(
    r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})-(?P<H>\d{2})h(?P<M>\d{2})"
    r"(?:-(?P<week>\d{4}-S\d{2})-(?P<poster>.+?\.(?:jpg|jpeg|png|webp)))?\.txt$",
    re.IGNORECASE,
)

def _parse_post_filename(filename: str) -> tuple[datetime | None, str | None, str | None]:
    """Extrait (datetime Europe/Paris, week_dir_name, poster_filename) depuis le nom de fichier.

    Gère:
      - Nouveau format: YYYY-MM-DD-HHhMM-YYYY-SWW-<poster>.<ext>.txt
      - Ancien format: YYYY-MM-DD-HHhMM.txt (week_dir_name et poster_filename seront None)
    """
    m = _POST_FILENAME_RE.match(filename)
    if not m:
        return (None, None, None)
    try:
        year = int(m.group("y"))
        month = int(m.group("m"))
        day = int(m.group("d"))
        hour = int(m.group("H"))
        minute = int(m.group("M"))
        week = m.group("week")
        poster = m.group("poster")
        paris_tz = tz.gettz("Europe/Paris")
        dt = datetime(year, month, day, hour, minute, tzinfo=paris_tz)
        return (dt, week, poster)
    except Exception:
        return (None, None, None)

def _to_utc_epoch_seconds(local_dt: datetime) -> int:
    """Convertit un datetime aware (Europe/Paris) vers un timestamp Unix UTC (secondes)."""
    dt_utc = local_dt.astimezone(timezone.utc)
    return int(dt_utc.timestamp())

def _read_text(filepath: Path) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read().strip()

def _schedule_facebook_post(message: str, scheduled_publish_time_utc: int) -> dict | None:
    """Crée un post programmé sur la Page Facebook.
    Retourne le JSON de réponse en cas de succès, None sinon.
    """
    if not PAGE_ACCESS_TOKEN or not FACEBOOK_PAGE_ID:
        print("Erreur : PAGE_ACCESS_TOKEN ou FACEBOOK_PAGE_ID manquant(s)")
        return None

def _schedule_facebook_photo(caption: str, image_path: Path, scheduled_publish_time_utc: int) -> dict | None:
    """Programme un post Facebook avec image (photo) sur la Page.
    Utilise l'endpoint /{page-id}/photos avec published=false et scheduled_publish_time.
    """
    if not PAGE_ACCESS_TOKEN or not FACEBOOK_PAGE_ID:
        print("Erreur : PAGE_ACCESS_TOKEN ou FACEBOOK_PAGE_ID manquant(s)")
        return None

    url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/photos"
    data = {
        "access_token": PAGE_ACCESS_TOKEN,
        "caption": caption,
        "published": "false",
        "scheduled_publish_time": scheduled_publish_time_utc,
    }
    try:
        with open(image_path, "rb") as fp:
            files = {"source": fp}
            resp = requests.post(url, data=data, files=files)
            resp.raise_for_status()
            return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la programmation du post photo ({scheduled_publish_time_utc}) : {e}")
        try:
            print(f"Détails : {resp.json()}")
        except Exception:
            print(f"Contenu brut : {resp.text if 'resp' in locals() else 'non dispo'}")
        return None

    url = f"https://graph.facebook.com/v23.0/{FACEBOOK_PAGE_ID}/feed"
    payload = {
        "access_token": PAGE_ACCESS_TOKEN,
        "message": message,
        "published": "false",
        "scheduled_publish_time": scheduled_publish_time_utc,
    }
    try:
        resp = requests.post(url, data=payload)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la programmation du post ({scheduled_publish_time_utc}) : {e}")
        try:
            print(f"Détails : {resp.json()}")
        except Exception:
            print(f"Contenu brut : {resp.text if 'resp' in locals() else 'non dispo'}")
        return None

def sync_posts_from_directory(posts_dir: str | Path) -> None:
    """Parcourt le dossier `posts` et programme les posts futurs manquants.
    - Filtre: fichiers au format YYYY-MM-DD-HHhMM.txt
    - Fuseau: Europe/Paris -> conversion en timestamp Unix UTC pour l'API Graph
    - Ignore si un post (ou vidéo) est déjà programmé exactement à ce timestamp
    """
    base_dir = Path(posts_dir)
    if not base_dir.exists() or not base_dir.is_dir():
        print(f"Dossier introuvable: {base_dir}")
        return

    already_scheduled = _collect_scheduled_timestamps()
    now_paris = datetime.now(tz.gettz("Europe/Paris"))

    created_count = 0
    skipped_existing = 0
    skipped_past = 0
    scanned = 0

    posters_base = base_dir.parent / "posters"

    for entry in sorted(base_dir.iterdir()):
        if not entry.is_file():
            continue
        local_dt, week_dir_name, poster_filename = _parse_post_filename(entry.name)
        if local_dt is None:
            continue
        scanned += 1

        if local_dt <= now_paris:
            skipped_past += 1
            continue

        ts_utc = _to_utc_epoch_seconds(local_dt)

        if ts_utc in already_scheduled:
            skipped_existing += 1
            continue

        message = _read_text(entry)
        if not message:
            print(f"Fichier vide, ignoré: {entry.name}")
            continue

        # Tenter un post avec image si les éléments sont présents et le fichier existe
        res = None
        image_path: Path | None = None
        if week_dir_name and poster_filename:
            candidate = posters_base / week_dir_name / poster_filename
            if candidate.exists() and candidate.is_file():
                image_path = candidate
                res = _schedule_facebook_photo(message, image_path, ts_utc)

        # Fallback: post texte si échec ou pas d'image
        if res is None:
            res = _schedule_facebook_post(message, ts_utc)
        if res is not None:
            created_count += 1
            already_scheduled.add(ts_utc)
            if image_path is not None:
                print(f"✓ Programmé (image): {entry.name} -> {ts_utc} | img={image_path}")
            else:
                print(f"✓ Programmé (texte): {entry.name} -> {ts_utc}")
        else:
            print(f"✗ Échec programmation: {entry.name}")

    print(
        f"Terminé. Fichiers scannés: {scanned}, créés: {created_count}, déjà présents: {skipped_existing}, passés: {skipped_past}"
    )

if __name__ == "__main__":
    import sys
    
    # Si l'argument "--get-token" est passé, générer un nouveau token
    if len(sys.argv) > 1 and sys.argv[1] == "--get-token":
        get_long_lived_page_token()
    elif len(sys.argv) > 1 and sys.argv[1] == "--list":
        get_scheduled_posts()
    else:
        # Par défaut: synchroniser les fichiers du dossier posts -> posts programmés Facebook
        script_dir = Path(__file__).resolve().parent
        posts_path = script_dir / "posts"
        sync_posts_from_directory(posts_path)
