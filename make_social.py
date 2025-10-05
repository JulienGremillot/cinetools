
import os
import json
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

load_dotenv()

OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma2"

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def query_llm(payload):
    prompt = payload["inputs"]
    data = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(OLLAMA_API_URL, headers=headers, json=data, timeout=300)
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
        json_response = response.json()
        if "response" in json_response:
            return [{"generated_text": json_response["response"]}]
        else:
            print(f"Erreur ou réponse vide de l'API Ollama: {json_response}")
            raise Exception("Réponse vide ou invalide d'Ollama")
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l'appel à l'API Ollama: {e}")
        raise

def main():
    seances_dir = "seances"
    current_date = datetime.now()

    # Déterminer la semaine ISO (YYYY-Www)
    # Le format de fichier est YYYY-Sww, donc nous devons ajuster un peu
    year = current_date.year
    week_number = current_date.isocalendar()[1] # isocalendar()[1] donne le numéro de semaine ISO

    # Formatage pour correspondre à 2025-S36.json
    file_pattern = f"{year}-S{{:02d}}.json"
    current_week_file = file_pattern.format(week_number)

    if not os.path.exists("posts"):
        os.makedirs("posts")

    # Boucler sur les fichiers de séance
    for i in range(10):  # Boucler sur 10 semaines, à ajuster si nécessaire
        target_file = os.path.join(seances_dir, current_week_file)
        if os.path.exists(target_file):
            print(f"Lecture du fichier : {target_file}")
            with open(target_file, 'r', encoding='utf-8') as f:
                seances_data = json.load(f)

            for film in seances_data:
                titre = film.get("titre", "")
                seances = film.get("seances", [])
                description = film.get("description", "")
                url_youtube = film.get("url_youtube", "")

                if not all([titre, seances, description, url_youtube]):
                    print(f"Informations manquantes pour un film dans {target_file}, ignoré.")
                    continue

                # Utilise le format complet de la première séance
                first_seance_date = datetime.strptime(seances[0], "%Y-%m-%dT%H:%M:%S")
                post_date = first_seance_date - timedelta(hours=48)
                output_filename = post_date.strftime("%Y-%m-%d-%Hh%M.txt")
                output_filepath = os.path.join("posts", output_filename)

                if os.path.exists(output_filepath):
                    print(f"Le fichier de destination {output_filepath} existe déjà. Passage au film suivant.")
                    continue

                prompt = f"""
                Rédige un post sympa et attrayant pour Instagram et Facebook pour annoncer le film "{titre}".
                Le film sera projeté aux dates et heures suivantes : {', '.join(seances)}.
                Voici une brève description du film : {description}.
                N'oublie pas d'inclure le lien de la bande-annonce YouTube au format texte : {url_youtube}
                Ajoute quelques hashtags pertinents pour le cinéma, la sortie de film et les réseaux sociaux.
                Le post doit être engageant et inciter les gens à venir voir le film.
                Écris en texte brut, sans utiliser de markdown (pas de ##, pas de **, pas de crochets ou parenthèses
                 de lien). Mets en valeur avec des emojis et des phrases courtes et dynamiques.
                N'incite pas les gens à réserver leurs places, car notre cinéma ne propose pas encore ce service.
                """

                print(f"Envoi du prompt pour '{titre}'...")
                payload = {"inputs": prompt}
                try:
                    response = query_llm(payload)
                except RetryError as e:
                    print(f"Erreur de réessai pour '{titre}': {e}")
                    continue

                if response and isinstance(response, list) and 'generated_text' in response[0]:
                    generated_text = response[0]['generated_text']
                    # Le texte généré contient souvent le prompt en entier, il faut l'extraire
                    # On cherche la partie du texte qui est après le prompt initial.
                    # Cela peut être un peu délicat avec Mistral, il est souvent utile de
                    # demander au LLM de générer seulement la réponse.
                    # Pour l'instant, on va juste prendre la fin.
                    # Une approche plus robuste serait d'avoir un modèle qui répond spécifiquement.

                    # Tentons de trouver la fin du prompt pour extraire la réponse
                    # Ceci est une heuristique et pourrait nécessiter des ajustements
                    post_content = generated_text.replace(prompt, "").strip()

                    with open(output_filepath, 'w', encoding='utf-8') as f:
                        f.write(post_content)
                    print(f"Post sauvegardé dans : {output_filepath}")
                else:
                    print(f"Erreur ou réponse vide de l'API Ollama pour '{titre}': {response}")
        else:
            print(f"Fichier non trouvé : {target_file}. Arrêt de la boucle.")
            break

        # Préparer pour la semaine suivante
        current_date += timedelta(weeks=1)
        year = current_date.year
        week_number = current_date.isocalendar()[1]
        current_week_file = file_pattern.format(week_number)

if __name__ == "__main__":
    main()
