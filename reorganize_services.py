import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "heavenprem.db")

CATEGORIES = {
    "🤖 Intelligence Artificielle": [3, 5, 6, 7, 10, 12, 13, 14, 15, 20, 23, 26],
    "🎬 Design & Vidéo": [1, 2, 8, 9, 18, 21, 22],
    "🛡️ Sécurité & Outils": [4, 11, 16, 17, 19, 24, 25]
}

def reorganize():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ajouter une colonne catégorie si elle n'existe pas
    try:
        cursor.execute("ALTER TABLE services ADD COLUMN category TEXT")
    except sqlite3.OperationalError:
        pass # déjà existante
    
    # Mettre à jour les catégories
    for cat, sids in CATEGORIES.items():
        for sid in sids:
            cursor.execute("UPDATE services SET category = ? WHERE id = ?", (cat, sid))
    
    # Améliorer les noms et emojis
    updates = [
        (1, "🎨 Canva Pro", "🎨"),
        (2, "🎬 CapCut VIP", "🎬"),
        (3, "🤖 ChatGPT Plus", "🤖"),
        (4, "🎮 Discord Nitro", "🎮"),
        (5, "✨ Gemini Advanced", "✨"),
        (6, "🧠 Grok AI", "🧠"),
        (7, "🚀 Manus AI Pro", "🚀"),
        (25, "🛡️ VPN Premium", "🛡️"),
        (20, "🔍 Perplexity Pro", "🔍"),
        (19, "📧 Outlook Business", "📧")
    ]
    
    for sid, name, emoji in updates:
        cursor.execute("UPDATE services SET name = ?, emoji = ? WHERE id = ?", (name, emoji, sid))
        
    conn.commit()
    conn.close()
    print("Services réorganisés avec succès.")

if __name__ == "__main__":
    reorganize()
