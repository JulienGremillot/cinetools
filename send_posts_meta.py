
import os
import requests
from dotenv import load_dotenv

load_dotenv()

META_LONG_LIVED_TOKEN = os.getenv("META_LONG_LIVED_TOKEN")
META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")

def get_scheduled_posts():
    if not META_LONG_LIVED_TOKEN:
        print("Erreur : Le token META_LONG_LIVED_TOKEN n'est pas configuré dans le fichier .env")
        return
    
    if not FACEBOOK_PAGE_ID:
        print("Erreur : L'ID de la page Facebook n'est pas configuré. Veuillez définir 'FACEBOOK_PAGE_ID' dans le fichier .env.")
        return

    # Pour Facebook posts programmés
    # doc: https://developers.facebook.com/docs/graph-api/reference/page/scheduled_posts/
    facebook_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/scheduled_posts"
    params = {
        "access_token": META_LONG_LIVED_TOKEN,
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
    # Note: L'API Instagram Business ne liste pas directement les "scheduled_posts" comme Facebook.
    # Il faut généralement interroger tous les médias et filtrer par 'status_code' ou 'is_published'
    # Cependant, il n'y a pas de champ direct 'scheduled_publish_time' pour les médias Instagram via l'API
    # Une approche serait de regarder les publications qui sont en 'SCHEDULED' statut si elles sont disponibles.
    # Pour l'instant, nous allons nous concentrer sur la récupération des publications Facebook programmées.
    # Pour Instagram, il faudrait une logique plus complexe pour simuler la vue du calendrier.
    print("\n--- Vérification des publications Instagram programmées (fonctionnalité à développer) ---")
    print("L'API Instagram Business n'offre pas de moyen direct de lister les publications programmées comme Facebook.")
    print("Pour une vérification complète, il faudrait une approche plus complexe (ex: vérifier les publications non publiées avec une date future). J'ai ajouté un TODO dans le code pour cela.")

if __name__ == "__main__":
    get_scheduled_posts()
