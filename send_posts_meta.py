
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import dateutil.parser

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

if __name__ == "__main__":
    import sys
    
    # Si l'argument "--get-token" est passé, générer un nouveau token
    if len(sys.argv) > 1 and sys.argv[1] == "--get-token":
        get_long_lived_page_token()
    else:
        get_scheduled_posts()
