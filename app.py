import os
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = 'reussite_samake_secret_key_2026'

# Votre code PIN maître à 4 chiffres
CODE_PIN_VALIDE = "7827"

@app.route('/')
def index():
    # Vérifie si l'utilisateur est déjà connecté avec le PIN
    if not session.get('authentifie'):
        return redirect(url_for('connexion'))
    return render_template('index.html')

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        # Récupère le code PIN saisi dans le formulaire
        pin_saisi = request.form.get('pin') or request.form.get('code') or request.form.get('password')
        
        if pin_saisi == CODE_PIN_VALIDE:
            session['authentifie'] = True
            session['user'] = 'Mouhamet'
            return redirect(url_for('index'))
        else:
            flash("Code PIN incorrect. Veuillez réessayer.")
            
    return render_template('connexion.html')

@app.route('/deconnexion')
def deconnexion():
    session.clear()
    return redirect(url_for('connexion'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
