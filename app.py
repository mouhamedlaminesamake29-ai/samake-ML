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
        <p>Entrez le code PIN (2026)</p>
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
    <title>Plateforme Pro - Réussite+</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; color: #333; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1 { color: #2c3e50; text-align: center; margin-bottom: 5px; }
        .subtitle { text-align: center; color: #7f8c8d; margin-bottom: 30px; }
        
        .tabs { display: flex; justify-content: center; gap: 10px; margin-bottom: 30px; flex-wrap: wrap; }
        .tab-btn { padding: 10px 20px; border: none; background: #e0e0e0; cursor: pointer; font-weight: bold; border-radius: 8px; transition: 0.3s; }
        .tab-btn.active { background: #3498db; color: white; }
        
        .section { display: none; }
        .section.active { display: block; }
        
        .card-box { background: #f9f9f9; padding: 20px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #3498db; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
        input, select { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }
        
        .btn-main { background: #2ecc71; color: white; padding: 12px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; font-size: 16px; }
        .btn-main:hover { background: #27ae60; }
        
        /* Chronomètre */
        .chrono-display { font-size: 42px; text-align: center; font-weight: bold; color: #2c3e50; margin: 20px 0; background: #fff; padding: 15px; border-radius: 10px; border: 2px dashed #3498db; }
        .chrono-btns { display: flex; gap: 10px; }
        
        ul { list-style: none; padding: 0; }
        li { background: white; padding: 12px; margin-bottom: 10px; border-radius: 6px; box-shadow: 0 2px 5px rgba(0,0,0,0.03); display: flex; justify-content: space-between; align-items: center; border-left: 4px solid #2ecc71; }
        
        .btn-logout { display: block; text-align: center; margin-top: 40px; color: #e74c3c; text-decoration: none; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Réussite+ Pro</h1>
        <div class="subtitle">Espace d'Organisation, Minuteur & Préparation aux Examens (Bac / Compositions)</div>
        
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('planning')">📅 Planning & Alarmes</button>
            <button class="tab-btn" onclick="switchTab('chrono')">⏱️ Minuteur d'Études</button>
            <button class="tab-btn" onclick="switchTab('examens')">📚 Prépa Bac & Devoirs</button>
        </div>

        <!-- ONGLET 1 : PLANNING & ALARMES -->
        <div id="planning" class="section active">
            <div class="card-box">
                <h3>Ajouter une session de révision</h3>
                <div class="form-group">
                    <label>Matière :</label>
                    <input type="text" id="matiere" placeholder="Ex: Mathématiques, Physique-Chimie...">
                </div>
                <div class="form-group">
                    <label>Heure de l'alarme :</label>
                    <input type="time" id="heure">
                </div>
                <button class="btn-main" onclick="ajouterTache()">Enregistrer et Activer l'Alarme</button>
            </div>
            <h3>Mes révisions enregistrées (Hors ligne)</h3>
            <ul id="listeTaches"></ul>
        </div>

        <!-- ONGLET 2 : CHRONOMÈTRE / MINUTEUR -->
        <div id="chrono" class="section">
            <div class="card-box" style="text-align: center;">
                <h3>Mode Concentration & Session Chrono</h3>
                <p>Idéal pour travailler en blocs de 25 minutes (Méthode Pomodoro).</p>
                <div class="chrono-display" id="timerDisplay">25:00</div>
                <div style="display: flex; gap: 10px; justify-content: center;">
                    <button class="tab-btn active" onclick="startTimer()" style="background: #2ecc71; color:white;">Démarrer</button>
                    <button class="tab-btn" onclick="pauseTimer()" style="background: #e67e22; color:white;">Pause</button>
                    <button class="tab-btn" onclick="resetTimer()" style="background: #e74c3c; color:white;">Réinitialiser</button>
                </div>
            </div>
        </div>

        <!-- ONGLET 3 : PRÉPA EXAMENS & DEVOIRS -->
        <div id="examens" class="section">
            <div class="card-box">
                <h3>Sujets & Exercices Clés (Bac & Compositions)</h3>
                <p>Rappels essentiels pour réussir vos épreuves :</p>
                <ul style="margin-top: 15px;">
                    <li><strong>Sciences Physiques :</strong> Chimie organique (Formules brutes, semi-développées) & Mécanique (Plans inclinés, théorèmes de l'énergie cinétique).</li>
                    <li><strong>Mathématiques :</strong> Suites numériques, Études de fonctions, Probabilités et Nombres complexes.</li>
                    <li><strong>Philosophie / Lettres :</strong> Méthodologie de la dissertation et du commentaire de texte.</li>
                </ul>
            </div>
            <div class="card-box">
                <h3>Ajouter un devoir ou un rappel d'examen</h3>
                <div class="form-group">
                    <label>Intitulé du Devoir / Examen :</label>
                    <input type="text" id="nomDevoir" placeholder="Ex: Devoir n°2 de Physique">
                </div>
                <div class="form-group">
                    <label>Date limite :</label>
                    <input type="date" id="dateDevoir">
                </div>
                <button class="btn-main" onclick="ajouterDevoir()">Ajouter à la liste des devoirs</button>
            </div>
            <h3>Devoirs à rendre</h3>
            <ul id="listeDevoirs"></ul>
        </div>

        <a href="/deconnexion" class="btn-logout">Se déconnecter</a>
    </div>

    <script>
        // Gestion des onglets
        function switchTab(tabId) {
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.currentTarget.classList.add('active');
        }

        // --- GESTION PLANNING & LOCALSTORAGE (Hors Ligne) ---
        let taches = JSON.parse(localStorage.getItem('taches_reussite')) || [];
        
        function chargerTaches() {
            const liste = document.getElementById('listeTaches');
            liste.innerHTML = '';
            if (taches.length === 0) {
                liste.innerHTML = '<li style="color: #999; justify-content: center;">Aucune révision enregistrée.</li>';
                return;
            }
            taches.forEach((t, index) => {
                liste.innerHTML += `<li><span><strong>${t.matiere}</strong> - ${t.heure}</span> <button onclick="supprimerTache(${index})" style="background:#e74c3c; color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">Supprimer</button></li>`;
            });
        }

        function ajouterTache() {
            const matiere = document.getElementById('matiere').value;
            const heure = document.getElementById('heure').value;
            if (!matiere || !heure) { alert('Remplissez tous les champs !'); return; }
            taches.push({ matiere, heure });
            localStorage.setItem('taches_reussite', JSON.stringify(taches));
            document.getElementById('matiere').value = '';
            document.getElementById('heure').value = '';
            chargerTaches();
            alert('Enregistré avec succès ! Vos données restent sauvegardées même hors connexion.');
        }

        function supprimerTache(index) {
            taches.splice(index, 1);
            localStorage.setItem('taches_reussite', JSON.stringify(taches));
            chargerTaches();
        }

        // --- GESTION DEVOIRS & EXAMENS ---
        let devoirs = JSON.parse(localStorage.getItem('devoirs_reussite')) || [];
        
        function chargerDevoirs() {
            const liste = document.getElementById('listeDevoirs');
            liste.innerHTML = '';
            if (devoirs.length === 0) {
                liste.innerHTML = '<li style="color: #999; justify-content: center;">Aucun devoir enregistré.</li>';
                return;
            }
            devoirs.forEach((d, index) => {
                liste.innerHTML += `<li><span><strong>${d.nomDevoir}</strong> (Pour le : ${d.dateDevoir})</span> <button onclick="supprimerDevoir(${index})" style="background:#e74c3c; color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">Fait</button></li>`;
            });
        }

        function ajouterDevoir() {
            const nomDevoir = document.getElementById('nomDevoir').value;
            const dateDevoir = document.getElementById('dateDevoir').value;
            if (!nomDevoir || !dateDevoir) { alert('Remplissez tous les champs !'); return; }
            devoirs.push({ nomDevoir, dateDevoir });
            localStorage.setItem('devoirs_reussite', JSON.stringify(devoirs));
            document.getElementById('nomDevoir').value = '';
            document.getElementById('dateDevoir').value = '';
            chargerDevoirs();
        }

        function supprimerDevoir(index) {
            devoirs.splice(index, 1);
            localStorage.setItem('devoirs_reussite', JSON.stringify(devoirs));
            chargerDevoirs();
        }

        // --- MINUTEUR / CHRONO AUTOMATIQUE ---
        let timerInterval;
        let timeLeft = 25 * 60; // 25 minutes

        function updateTimerDisplay() {
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            document.getElementById('timerDisplay').innerText = 
                `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }

        function startTimer() {
            if (timerInterval) return;
            timerInterval = setInterval(() => {
                if (timeLeft > 0) {
                    timeLeft--;
                    updateTimerDisplay();
                } else {
                    clearInterval(timerInterval);
                    timerInterval = null;
                    alert("⏰ Fin de la session de travail ! Prenez une pause méritée.");
                }
            }, 1000);
        }

        function pauseTimer() {
            clearInterval(timerInterval);
            timerInterval = null;
        }

        function resetTimer() {
            pauseTimer();
            timeLeft = 25 * 60;
            updateTimerDisplay();
        }

        // Surveillance automatique des alarmes en arrière-plan
        setInterval(() => {
            const now = new Date();
            const currentStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
            taches.forEach(t => {
                if (t.heure === currentStr && !t.notifie) {
                    t.notifie = true;
                    alert(`🚨 ALARME RÉVISION : C'est l'heure de travailler la matière : ${t.matiere} !`);
                }
            });
        }, 10000);

        // Chargement initial au démarrage
        window.onload = function() {
            chargerTaches();
            chargerDevoirs();
            updateTimerDisplay();
        };
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
