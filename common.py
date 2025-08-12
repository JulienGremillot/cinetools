from __future__ import annotations
import re
import unicodedata

def sanitize_filename(name: str, max_length: int = 150) -> str:
    """
    Nettoie un titre pour en faire un nom de fichier sûr, multi-plateforme.
    - Normalise Unicode
    - Remplace les séparateurs et caractères interdits
    - Supprime les caractères de contrôle
    - Evite les noms réservés Windows
    - Tronque si trop long
    """
    if not name:
        return "fichier"

    # Normalisation Unicode
    cleaned = unicodedata.normalize("NFKC", name)

    # Remplacement des séparateurs de chemin par un tiret
    cleaned = re.sub(r"[\\/]+", "-", cleaned)

    # Suppression des caractères de contrôle
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned)

    # Remplacement des caractères invalides pour Windows
    cleaned = re.sub(r'[<>:"|?*]', "_", cleaned)

    # Remplacement des espaces multiples par un seul, puis espaces -> underscore
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace(" ", "_")

    # Pas de point ni d'espace en fin de nom sur Windows
    cleaned = cleaned.rstrip(" .")

    # Noms réservés Windows
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if cleaned.upper() in reserved:
        cleaned = f"_{cleaned}"

    # Valeur de secours
    if not cleaned:
        cleaned = "fichier"

    # Tronque si nécessaire
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip("._- ")

    return cleaned
