import os
from flask import Flask, request, redirect, url_for, session, render_template_string

app = Flask(__name__)
app.secret_key = 'reussite_samake_secret_key_2026'

CODE_PIN_VALIDE = "2026"

PAGE_CONNEXION_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connexion - Réussite+</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f6f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; width: 300px; }
        h2 { margin-bottom: 20px; color: #333; }
        input[type="password"] { width: 100%; padding: 12px; font-size: 18px; text-align: center; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; margin-bottom: 15px; letter-spacing: 4px; }
        button { width: 100%; padding: 12px; font-size: 16px; background: #007bff; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; }
        button:hover { background: #0056b3; }
        .error { color: #d9534f; margin-bottom: 15px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Entrez le code PIN</h2>
        {% if erreur %}
            <div class="error">{{ erreur }}</div>
        {% endif %}
        <form method="POST">
            <input type="password" name="pin" placeholder="••••" maxlength="8" required autofocus autocomplete="off">
            <button type="submit">Valider</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    if not session.get('authentifie'):
        return redirect(url_for('connexion'))
    try:
        return render_template('index.html')
    except Exception:
        return "<h1>Bienvenue sur Réussite+</h1><p>Connexion réussie avec succès !</p><a href='/deconnexion'>Déconnexion</a>"

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    erreur = None
    if request.method == 'POST':
        pin_saisi = request.form.get('pin')
        if pin_saisi == CODE_PIN_VALIDE:
            session['authentifie'] = True
            return redirect(url_for('index'))
        else:
            erreur = "Code PIN incorrect."
            
    return render_template_string(PAGE_CONNEXION_HTML, erreur=erreur)

@app.route('/deconnexion')
def deconnexion():
    session.clear()
    return redirect(url_for('connexion'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
