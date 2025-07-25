import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List


# Chargement des variables d'environnement
load_dotenv()

@dataclass
class Film:
    titre: str
    duree: str
    art_et_essai: str
    visa: str
    support: str
    pourcentage: str
    version: str
    distributeur: str
    publicite: str


@dataclass
class SemaineProgrammation:
    date: str
    films: List[Film]

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
            'mdp': os.getenv('CINEMA_PASSWORD'),  # le champ s'appelle 'mdp' et non 'password'
            'sublogin': '1'  # champ caché nécessaire
        }
        
        # On fait d'abord une requête GET pour obtenir les éventuels cookies de session
        self.session.get(self.login_url)
        
        # L'URL de connexion correcte est process.php
        login_process_url = f"{self.base_url}/process.php"
        response = self.session.post(login_process_url, data=login_data)
        
        if response.ok:
            print("Connexion réussie")
            return True
        else:
            print(f"Échec de la connexion: {response.status_code}")
            print(f"Contenu de la réponse: {response.text}")
            return False

    def parse_film_row(self, row):  # Ajout de self
        """Parse une ligne du tableau contenant les informations d'un film"""
        cells = row.find_all('td')
        return Film(
            titre=cells[0].text.strip(),
            duree=cells[1].text.strip(),
            art_et_essai=cells[2].text.strip(),
            visa=cells[3].text.strip(),
            support=cells[4].text.strip(),
            pourcentage=cells[5].text.strip(),
            version=cells[6].text.strip(),
            distributeur=cells[7].text.strip(),
            publicite=cells[8].text.strip()
        )

    def parse_program_html(self, html_content: str) -> List[SemaineProgrammation]:
        """Parse le contenu HTML de la page de programmation"""
        from datetime import datetime
        import os
        
        soup = BeautifulSoup(html_content, 'html.parser')
        program = []

        # Trouver toutes les sections de semaine
        semaines = soup.find_all('h3')
        if semaines:
            print(f"Récupération des programmes pour {len(semaines)} semaines...")
        else:
            print("Aucune semaine trouvée")
            print(f"HTML téléchargé: {html_content}")

        for semaine in semaines:
            date_semaine = semaine.text.replace("Semaine du ", "")
            
            # Parser la date (format DD/MM/YYYY)
            date_obj = datetime.strptime(date_semaine, "%d/%m/%Y")
            annee = date_obj.strftime("%Y")
            num_semaine = date_obj.strftime("%V")

            # Trouver le tableau qui suit directement cette semaine
            table = semaine.find_next('table')
            if not table:
                continue

            # Parser chaque ligne de film dans le tableau
            films = []
            for row in table.find_all('tr')[1:]:  # Skip header row
                film = self.parse_film_row(row)  # Utilisation de self.parse_film_row
                films.append(film)

            # Créer le répertoire 'films' s'il n'existe pas
            os.makedirs('films', exist_ok=True)
            
            # Sauvegarder les titres dans un fichier
            filename = f"films/{annee}-S{num_semaine}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                for film in films:
                    f.write(f"{film.titre}\n")

            program.append(SemaineProgrammation(
                date=date_semaine,
                films=films
            ))

        return program

    def print_program(self, program: List[SemaineProgrammation]):  # Ajout de self
        """Affiche le programme de manière formatée"""
        for semaine in program:
            print(f"\n=== {semaine.date} ===")
            for film in semaine.films:
                print(f"\nFilm: {film.titre}")
                print(f"  Durée: {film.duree}")
                print(f"  Art&Essai: {film.art_et_essai}")
                print(f"  Visa: {film.visa}")
                print(f"  Support: {film.support}")
                print(f"  Pour%: {film.pourcentage}")
                print(f"  Version: {film.version}")
                print(f"  Distributeur: {film.distributeur}")
                print(f"  Publicité: {film.publicite}")

    def get_program(self):
        """Récupère le programme des films"""
        response = self.session.get(self.program_url)
        if response.ok:
            program = self.parse_program_html(response.text)
            if program:
                self.print_program(program)
                return program
            else:
                print("Échec du parsing du programme")
                return None
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