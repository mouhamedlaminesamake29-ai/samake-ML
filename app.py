import os
from flask import Flask, request, redirect, url_for, session, render_template_string

app = Flask(__name__)
app.secret_key = 'reussite_samake_ultra_secure_key_2026'

CODE_PIN_VALIDE = "2026"

PAGE_CONNEXION_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Accès Sécurisé - Réussite+</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 40px 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); text-align: center; width: 320px; }
        h2 { margin-bottom: 10px; color: #2c3e50; font-size: 24px; }
        p { color: #7f8c8d; font-size: 14px; margin-bottom: 25px; }
        input[type="password"] { width: 100%; padding: 14px; font-size: 24px; text-align: center; border: 2px solid #dcdde1; border-radius: 8px; box-sizing: border-box; margin-bottom: 20px; letter-spacing: 8px; outline: none; transition: border-color 0.3s; }
        input[type="password"]:focus { border-color: #3498db; }
        button { width: 100%; padding: 14px; font-size: 16px; background: #3498db; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; transition: background 0.3s; }
        button:hover { background: #2980b9; }
        .error { background: #ffeaa7; color: #d63031; padding: 10px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Réussite+</h2>
        <p>Veuillez entrer votre code PIN</p>
        {% if erreur %}
            <div class="error">{{ erreur }}</div>
        {% endif %}
        <form method="POST">
            <input type="password" name="pin" placeholder="••••" maxlength="4" required autofocus autocomplete="off">
            <button type="submit">Déverrouiller</button>
        </form>
    </div>
</body>
</html>
"""

PAGE_ACCUEIL_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Planning & Organisation - Réussite+</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 700px; margin: 0 auto; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1 { color: #2c3e50; text-align: center; }
        .planner-section { margin-top: 30px; border-top: 2px solid #eee; padding-top: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
        input, select { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
        .btn-add { background: #2ecc71; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; }
        .btn-add:hover { background: #27ae60; }
        ul { list-style: none; padding: 0; margin-top: 20px; }
        li { background: #f9f9f9; padding: 12px; margin-bottom: 10px; border-radius: 6px; border-left: 5px solid #3498db; display: flex; justify-content: space-between; align-items: center; }
        .btn-logout { display: block; text-align: center; margin-top: 40px; color: #e74c3c; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Réussite+ : Planning d'Études</h1>
        <p style="text-align: center; color: #7f8c8d;">Organisez vos révisions et recevez vos alertes de travail.</p>
        
        <div class="planner-section">
            <h3>Programmer une session</h3>
            <div class="form-group">
                <label for="matiere">Matière ou Tâche :</label>
                <input type="text" id="matiere" placeholder="Ex: Mathématiques / Physique">
            </div>
            <div class="form-group">
                <label for="heure">Heure de l'alarme :</label>
                <input type="time" id="heure">
            </div>
            <button class="btn-add" onclick="ajouterTache()">Activer l'alarme</button>
        </div>

        <div class="planner-section">
            <h3>Mes Révisions en Cours</h3>
            <ul id="listeTaches">
                <li style="color: #999;">Aucune tâche programmée.</li>
            </ul>
        </div>

        <a href="/deconnexion" class="btn-logout">Se déconnecter</a>
    </div>

    <script>
        let taches = [];

        function ajouterTache() {
            const matiere = document.getElementById('matiere').value;
            const heure = document.getElementById('heure').value;
            
            if (!matiere || !heure) {
                alert("Veuillez remplir la matière et l'heure !");
                return;
            }

            taches.push({ matiere: matiere, heure: heure, sonne: false });
            mettreAJourAffichage();

            document.getElementById('matiere').value = '';
            document.getElementById('heure').value = '';
            alert("Alarme enregistrée avec succès ! Gardez la page ouverte pour recevoir l'alerte.");
        }

        function mettreAJourAffichage() {
            const liste = document.getElementById('listeTaches');
            if (taches.length === 0) {
                liste.innerHTML = '<li style="color: #999;">Aucune tâche programmée.</li>';
                return;
            }
            liste.innerHTML = '';
            taches.forEach((t) => {
                liste.innerHTML += `<li><span><strong>${t.matiere}</strong> - Prévu à ${t.heure}</span> <span style="color: #27ae60; font-weight: bold;">⏰ Actif</span></li>`;
            });
        }

        // Vérification automatique toutes les 10 secondes pour déclencher l'alarme
        setInterval(() => {
            const maintenant = new Date();
            const heures = String(maintenant.getHours()).padStart(2, '0');
            const minutes = String(maintenant.getMinutes()).padStart(2, '0');
            const heureActuelle = `${heures}:${minutes}`;

            taches.forEach((t) => {
                if (t.heure === heureActuelle && !t.sonne) {
                    t.sonne = true; // Empêche de répéter l'alarme en boucle
                    alert(`🚨 ALARME RÉVISION : C'est l'heure de travailler la matière : ${t.matiere} !`);
                }
            });
        }, 10000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    if not session.get('authentifie'):
        return redirect(url_for('connexion'))
    return render_template_string(PAGE_ACCUEIL_HTML)

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    erreur = None
    if request.method == 'POST':
        pin_saisi = request.form.get('pin')
        if pin_saisi == CODE_PIN_VALIDE:
            session['authentifie'] = True
            return redirect(url_for('index'))
        else:
            erreur = "Code PIN incorrect !"
            
    return render_template_string(PAGE_CONNEXION_HTML, erreur=erreur)

@app.route('/deconnexion')
def deconnexion():
    session.clear()
    return redirect(url_for('connexion'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
