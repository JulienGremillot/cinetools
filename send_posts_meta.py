
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import dateutil.parser

load_dotenv()

META_LONG_LIVED_TOKEN = os.getenv("META_LONG_LIVED_TOKEN") # Peut encore être utile pour d'autres opérations utilisateur si nécessaire
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")

def get_scheduled_posts():
    if not PAGE_ACCESS_TOKEN:
        print("Erreur : Le PAGE_ACCESS_TOKEN n'est pas configuré dans le fichier .env")
        return

    if not FACEBOOK_PAGE_ID:
        print("Erreur : L'ID de la page Facebook n'est pas configuré. Veuillez définir 'FACEBOOK_PAGE_ID' dans le fichier .env.")
        return

    # Récupérer l'ID du compte Instagram Business lié à la page Facebook
    instagram_business_account_id = None
    page_info_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}"
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
        instagram_business_account_id = None # S'assurer que la variable est définie même en cas d'erreur

    # Pour Facebook posts programmés
    # doc: https://developers.facebook.com/docs/graph-api/reference/page/scheduled_posts/
    facebook_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/scheduled_posts"
    params = {
        "access_token": PAGE_ACCESS_TOKEN, # Utilisation du PAGE_ACCESS_TOKEN ici
        "fields": "id,message,created_time,scheduled_publish_time,is_published"
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

    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des publications Facebook programmées : {e}")
    
    # Pour Instagram posts programmés
    # doc: https://developers.facebook.com/docs/instagram-api/reference/instagram-business-account/media#getting-scheduled-posts
    if instagram_business_account_id:
        instagram_url = f"https://graph.facebook.com/v19.0/{instagram_business_account_id}/media"
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
    get_scheduled_posts()
