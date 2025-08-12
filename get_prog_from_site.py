import json
import locale
from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

def _strip_accents(s: str) -> str:
    # Supprime les diacritiques pour pouvoir faire correspondre "août" et "aout"
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def _normalize_spaces(s: str) -> str:
    # Remplace les espaces insécables/narrow no-break par des espaces normaux et compresse
    s = s.replace("\u00A0", " ").replace("\u202F", " ")
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s).strip()

def _parse_date_fr(self, date_text: str) -> datetime.date:
    """
    Parse des dates françaises du type '13 août 2025' sans dépendre de la locale.
    Gère les espaces insécables, '1er', et les accents.
    """
    # Normalisations
    txt = _normalize_spaces(date_text).lower()
    # Remplace '1er' par '1'
    txt = re.sub(r"\b1\s*er\b", "1", txt)

    # Extrait jour, mois, année n'importe où dans la chaîne
    m = re.search(r"(?i)\b(\d{1,2})\s+([A-Za-zÀ-ÖØ-öø-ÿ\-]+)\s+(\d{4})\b", txt)
    if not m:
        raise ValueError(f"Format de date inattendu: {date_text!r}")

    day_str, month_str, year_str = m.groups()

    # Mapping des mois en français (avec variantes sans accent)
    mois_map = {
        "janvier": 1,
        "fevrier": 2, "février": 2,
        "mars": 3,
        "avril": 4,
        "mai": 5,
        "juin": 6,
        "juillet": 7,
        "aout": 8, "août": 8,
        "septembre": 9,
        "octobre": 10,
        "novembre": 11,
        "decembre": 12, "décembre": 12,
    }

    # Essaie direct, puis sans accents
    month_num = mois_map.get(month_str)
    if month_num is None:
        month_num = mois_map.get(_strip_accents(month_str))
    if month_num is None:
        raise ValueError(f"Mois français inconnu: {month_str!r} dans {date_text!r}")

    day = int(day_str)
    year = int(year_str)

    return datetime.date(year, month_num, day)


@dataclass
class Film:
    titre: str
    url_poster: str
    seances: List[datetime]


class CinemaParadiso:
    def __init__(self):
        self.base_url = "https://www.cinema-paradiso.asso.fr"
        self.program_url = f"{self.base_url}/programme"
        # Tentative de réglage de locale FR, tolérante selon l'OS
        for loc in ("fr_FR", "fr_FR.UTF-8", "French_France.1252"):
            try:
                locale.setlocale(locale.LC_TIME, loc)
                break
            except Exception:
                continue

    def _load_html(self, html_path: Optional[str]) -> str:
        """
        Charge le HTML depuis un fichier local si fourni/existant,
        sinon depuis l'URL distante.
        """
        if html_path:
            p = Path(html_path)
            if p.exists():
                return p.read_text(encoding="utf-8")

        # Détection automatique du fichier d'exemple si présent
        default = Path(__file__).parent / "examples" / "Cinema Paradiso Nort sur Erdre.html"
        if default.exists():
            return default.read_text(encoding="utf-8")

        # Fallback: récupération distante
        resp = requests.get(self.program_url, timeout=20)
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def _clean_spaces(s: str) -> str:
        return " ".join(s.split())

    @staticmethod
    def _parse_date_fr(date_text: str) -> datetime:
        # date_text comme "13 août 2025"
        return datetime.strptime(date_text, "%d %B %Y")

    def _extract_seance_dt(self, txt: str) -> Optional[datetime]:
        """
        Extrait un datetime depuis un texte d'horaire en français, ex:
        "mercredi 13 août 2025 20h30", en tolérant des suffixes (VO, Prochaine séance, ...).
        """
        txt = self._clean_spaces(txt)
        m = re.search(r"(\d{1,2}\s+\w+\s+\d{4}).*?(\d{1,2})h(\d{2})", txt, flags=re.IGNORECASE)
        if not m:
            return None
        date_part = m.group(1)
        hh = int(m.group(2))
        mm = int(m.group(3))
        try:
            d = self._parse_date_fr(date_part)
        except Exception:
            return None
        return d.replace(hour=hh, minute=mm, second=0, microsecond=0)

    def _find_week_sections(self, soup: BeautifulSoup):
        """
        Retourne une liste de tuples (section, date_debut_text)
        en repérant les blocs de semaine et la date de début.
        """
        results = []
        # Cible prioritaire: éléments avec la classe 'titre-semaine' dans des <section>
        for section in soup.find_all("section"):
            titre_elem = section.select_one(".titre-semaine")
            text = ""
            if titre_elem:
                text = self._clean_spaces(titre_elem.get_text(" ", strip=True))
            else:
                # Fallback: n'importe quel élément contenant "Semaine du"
                any_elem = section.find(string=lambda t: t and "Semaine du" in t)
                if any_elem:
                    text = self._clean_spaces(str(any_elem))

            if not text:
                continue

            m = re.search(r"Semaine du\s+(.+?)\s+au\s+(.+)", text, flags=re.IGNORECASE)
            if not m:
                continue

            date_debut_text = m.group(1).strip()
            results.append((section, date_debut_text))

        return results

    def parse_program(self, html_path: Optional[str] = None):
        html = self._load_html(html_path)
        soup = BeautifulSoup(html, "html.parser")

        semaines = self._find_week_sections(soup)
        print(f"Trouvé {len(semaines)} semaines...")

        for section, date_debut_text in semaines:
            print(f"Date de début : {date_debut_text}")
            try:
                date_debut = self._parse_date_fr(date_debut_text)
            except Exception as e:
                print(f"Impossible de parser la date de début '{date_debut_text}': {e}")
                continue

            num_semaine = date_debut.strftime("%V")
            annee = date_debut.strftime("%Y")

            films_by_titre: dict[str, Film] = {}

            # On récupère tous les horaires de la section
            horaire_divs = section.select(".horaire")
            for hdiv in horaire_divs:
                seance_txt = hdiv.get_text(" ", strip=True)
                dt = self._extract_seance_dt(seance_txt)
                if not dt:
                    continue

                # On remonte au dernier titre (h5) rencontré avant l'horaire
                titre_tag = hdiv.find_previous(["h5", "h4", "h3"])
                if not titre_tag:
                    continue

                titre = self._clean_spaces(titre_tag.get_text(" ", strip=True))

                # Initialise l'entrée film si besoin
                film = films_by_titre.get(titre)
                if not film:
                    # Tente de récupérer l'image (affiche) la plus proche dans le même bloc
                    poster_url = ""
                    # On remonte les ancêtres jusqu'à la section courante
                    for anc in titre_tag.parents:
                        if anc == section:
                            break
                        img = anc.find("img")
                        if img and img.get("src"):
                            poster_url = urljoin(self.base_url, img.get("src"))
                            break

                    film = Film(titre=titre, url_poster=poster_url, seances=[])
                    films_by_titre[titre] = film

                film.seances.append(dt)

            films = list(films_by_titre.values())
            for f in films:
                f.seances.sort()

            print(f"Trouvé {len(films)} films...")

            # Sauvegarde un JSON par semaine
            filename = f"seances/{annee}-S{num_semaine}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            "titre": film.titre,
                            "url_poster": film.url_poster,
                            "seances": [s.isoformat() for s in film.seances],
                        }
                        for film in films
                    ],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"Sauvegardé: {filename}")


def main():
    cinema = CinemaParadiso()
    # Laisse parse_program détecter automatiquement le fichier local d'exemple s'il existe,
    # sinon la page distante sera utilisée.
    cinema.parse_program()


if __name__ == "__main__":
    main()