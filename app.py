import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'reussite_samake_secret_key_2026'

# Chemin absolu garanti pour la base de données sur Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'reussite.db')

def init_db():
    """Initialise la base de données SQLite et vos accès maîtres."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Création de la table des utilisateurs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Vos accès maîtres automatiques
    mes_comptes = [
        ("Mouhamet", "Samake2026!"),
        ("admin", "admin123")
    ]
    
    for user, pwd in mes_comptes:
        cursor.execute("SELECT * FROM users WHERE username = ?", (user,))
        if not cursor.fetchone():
            hashed_pwd = generate_password_hash(pwd)
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user, hashed_pwd))
            print(f"--> Compte créé : {user}")
    
    conn.commit()
    conn.close()

# Création automatique de la base au lancement
init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        username = request.form.get('username') or request.form.get('email')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and (check_password_hash(user[0], password) or user[0] == password):
            session['user'] = username
            return redirect(url_for('index'))
        else:
            flash("Identifiant ou mot de passe incorrect.")
            
    return render_template('connexion.html')

@app.route('/deconnexion')
def deconnexion():
    session.pop('user', None)
    return redirect(url_for('connexion'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
