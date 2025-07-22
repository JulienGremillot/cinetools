import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

# Chargement des variables d'environnement
load_dotenv()

class CinemaClient:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.cinediffusion.fr/espace_adherents"
        self.login_url = f"{self.base_url}/index.php"
        self.program_url = f"{self.base_url}/admin_main.php?section=programmation"
        
    def login(self):
        """Se connecte à l'espace adhérents"""
        login_data = {
            'login': os.getenv('CINEMA_LOGIN'),
            'password': os.getenv('CINEMA_PASSWORD'),
            # Ajoutez d'autres champs si nécessaire selon le formulaire
        }
        
        response = self.session.post(self.login_url, data=login_data)
        if response.ok:
            print("Connexion réussie")
            return True
        else:
            print(f"Échec de la connexion: {response.status_code}")
            return False

    def get_program(self):
        """Récupère le programme des films"""
        response = self.session.get(self.program_url)
        if response.ok:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Ici, il faudra adapter le parsing selon la structure HTML de la page
            # Par exemple :
            # program = soup.find('div', class_='program-container')
            return response.text
        else:
            print(f"Échec de la récupération du programme: {response.status_code}")
            return None

def main():
    client = CinemaClient()
    if client.login():
        program = client.get_program()
        if program:
            print("Programme récupéré avec succès")
            # Traitement du programme...

if __name__ == "__main__":
    main()
