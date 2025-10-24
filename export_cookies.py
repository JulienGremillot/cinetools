#!/usr/bin/env python3
"""
Script pour exporter les cookies YouTube manuellement
Utilisez ce script si les cookies automatiques ne fonctionnent pas
"""

import os
import sqlite3
import json
import argparse
from pathlib import Path

def get_chrome_cookies_path():
    """Trouve le chemin vers la base de données des cookies Chrome"""
    possible_paths = [
        os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cookies"),
        os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Profile 1\\Cookies"),
        os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Profile 2\\Cookies"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def export_youtube_cookies(output_file="cookies.txt"):
    """Exporte les cookies YouTube vers un fichier au format Netscape"""
    cookies_path = get_chrome_cookies_path()
    
    if not cookies_path:
        print("❌ Base de données des cookies Chrome non trouvée")
        print("💡 Essayez de fermer Chrome complètement et relancez le script")
        return False
    
    if not os.path.exists(cookies_path):
        print(f"❌ Fichier cookies non trouvé : {cookies_path}")
        return False
    
    try:
        # Copier temporairement le fichier cookies (Chrome peut le verrouiller)
        import shutil
        temp_cookies = "temp_cookies.db"
        shutil.copy2(cookies_path, temp_cookies)
        
        # Connexion à la base de données
        conn = sqlite3.connect(temp_cookies)
        cursor = conn.cursor()
        
        # Récupérer les cookies YouTube
        cursor.execute("""
            SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly
            FROM cookies 
            WHERE host_key LIKE '%youtube.com%' OR host_key LIKE '%google.com%'
        """)
        
        cookies = cursor.fetchall()
        conn.close()
        
        # Nettoyer le fichier temporaire
        os.remove(temp_cookies)
        
        if not cookies:
            print("❌ Aucun cookie YouTube trouvé")
            return False
        
        # Écrire les cookies au format Netscape
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This is a generated file! Do not edit.\n\n")
            
            for cookie in cookies:
                name, value, domain, path, expires, secure, httponly = cookie
                
                # Convertir le timestamp Chrome (microsecondes depuis 1601) en timestamp Unix
                if expires:
                    # Chrome timestamp to Unix timestamp
                    expires_unix = (expires - 11644473600000000) // 1000000
                else:
                    expires_unix = 0
                
                # Format Netscape
                secure_flag = "TRUE" if secure else "FALSE"
                httponly_flag = "TRUE" if httponly else "FALSE"
                
                f.write(f"{domain}\t{secure_flag}\t{path}\t{secure_flag}\t{expires_unix}\t{name}\t{value}\n")
        
        print(f"✅ Cookies exportés vers : {output_file}")
        print(f"📊 {len(cookies)} cookies YouTube trouvés")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'export : {e}")
        print("💡 Assurez-vous que Chrome est fermé et relancez le script")
        return False

def main():
    parser = argparse.ArgumentParser(description="Exporte les cookies YouTube depuis Chrome")
    parser.add_argument("--output", "-o", default="cookies.txt", 
                       help="Fichier de sortie pour les cookies (défaut: cookies.txt)")
    
    args = parser.parse_args()
    
    print("🍪 Export des cookies YouTube...")
    print("⚠️  Assurez-vous que Chrome est fermé avant de continuer")
    
    if export_youtube_cookies(args.output):
        print(f"\n✅ Utilisez maintenant :")
        print(f"python get_bandes_annonces.py --cookies {args.output}")
    else:
        print(f"\n❌ Échec de l'export. Essayez :")
        print("1. Fermer Chrome complètement")
        print("2. Relancer ce script")
        print("3. Ou utiliser Firefox : python get_bandes_annonces.py --browser-cookies firefox")

if __name__ == "__main__":
    main()
