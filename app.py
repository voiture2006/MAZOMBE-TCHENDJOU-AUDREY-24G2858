from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
from datetime import datetime
import csv
import io
import math

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DATA_FILE = 'donner.json'

def load_data():
    """Charge toutes les données depuis le fichier unique"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'patients': []}

def save_data(data):
    """Sauvegarde toutes les données dans le fichier unique"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def calculer_niveau_risque(age, glycemie, tension, fumeur, taille):
    """Calcule le niveau de risque (Élevé/Modéré/Faible) selon les paramètres"""
    score = 0
    if age > 60:
        score += 2
    elif age > 45:
        score += 1
    if glycemie > 1.26:
        score += 2
    elif glycemie > 1.10:
        score += 1
    if tension == "Anormale":
        score += 2
    if fumeur == "Fumeur":
        score += 1
    if taille < 150:
        score += 1
    if score >= 5:
        return "Élevé"
    if score >= 3:
        return "Modéré"
    return "Faible"

@app.route('/')
def serve_index():
    return send_file('index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_file(path)

# PATIENTS
@app.route('/api/patients', methods=['GET'])
def get_patients():
    data = load_data()
    return jsonify(data['patients'])

@app.route('/api/patients', methods=['POST'])
def add_patient():
    try:
        data = load_data()
        req = request.json
        niveau_risque = calculer_niveau_risque(
            req.get('age', 0),
            req.get('glycemie', 0),
            req.get('tension', 'Normale'),
            req.get('fumeur', 'Non-fumeur'),
            req.get('taille', 170)
        )
        new_patient = {
            'id': int(datetime.now().timestamp() * 1000),
            'nom': req.get('nom'),
            'age': int(req.get('age', 0)),
            'sexe': req.get('sexe', 'Homme'),
            'taille': float(req.get('taille', 0)),
            'glycemie': float(req.get('glycemie', 0)),
            'tension': req.get('tension', 'Normale'),
            'fumeur': req.get('fumeur', 'Non-fumeur'),
            'contact': req.get('contact', ''),
            'niveau_risque': niveau_risque,
            'date_creation': datetime.now().isoformat()
        }
        data['patients'].append(new_patient)
        save_data(data)
        return jsonify(new_patient), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/patients/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    data = load_data()
    data['patients'] = [p for p in data['patients'] if p.get('id') != patient_id]
    save_data(data)
    return jsonify({'message': 'Patient supprimé'})

# RECHERCHE
@app.route('/api/recherche', methods=['GET'])
def search_patients():
    query = request.args.get('q', '').lower()
    risk = request.args.get('risk', 'all')
    data = load_data()
    patients = data['patients']
    
    if risk != 'all':
        patients = [p for p in patients if p.get('niveau_risque', '') == risk]
    if query:
        patients = [p for p in patients if query in p.get('nom', '').lower()]
    
    return jsonify(patients)

# STATISTIQUES
@app.route('/api/stats/medical', methods=['GET'])
def get_medical_stats():
    data = load_data()
    patients = data['patients']
    total = len(patients)
    
    risk_high = sum(1 for p in patients if p.get('niveau_risque') == 'Élevé')
    risk_moderate = sum(1 for p in patients if p.get('niveau_risque') == 'Modéré')
    risk_low = sum(1 for p in patients if p.get('niveau_risque') == 'Faible')
    
    avg_glycemia = sum(p.get('glycemie', 0) for p in patients) / total if total > 0 else 0
    avg_age = sum(p.get('age', 0) for p in patients) / total if total > 0 else 0
    
    smokers = sum(1 for p in patients if p.get('fumeur') == 'Fumeur')
    men = sum(1 for p in patients if p.get('sexe') == 'Homme')
    women = sum(1 for p in patients if p.get('sexe') == 'Femme')
    
    # Distribution par tranche d'âge
    age_distribution = {"0-30": 0, "31-50": 0, "51-70": 0, "70+": 0}
    for p in patients:
        age = p.get('age', 0)
        if age <= 30:
            age_distribution["0-30"] += 1
        elif age <= 50:
            age_distribution["31-50"] += 1
        elif age <= 70:
            age_distribution["51-70"] += 1
        else:
            age_distribution["70+"] += 1
    
    return jsonify({
        'total_patients': total,
        'risk_high_count': risk_high,
        'risk_moderate_count': risk_moderate,
        'risk_low_count': risk_low,
        'risk_high_percent': (risk_high/total*100) if total>0 else 0,
        'avg_glycemia': round(avg_glycemia, 2),
        'avg_age': round(avg_age, 1),
        'smoker_count': smokers,
        'smoker_percent': (smokers/total*100) if total>0 else 0,
        'gender_ratio': round(men/women, 2) if women>0 else men,
        'men_count': men,
        'women_count': women,
        'age_distribution': age_distribution
    })

# EXPORT CSV
@app.route('/api/export/patients', methods=['GET'])
def export_patients_csv():
    data = load_data()
    output = io.StringIO()
    fieldnames = ['id', 'nom', 'age', 'sexe', 'taille', 'glycemie', 'tension', 'fumeur', 'niveau_risque', 'contact', 'date_creation']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for p in data['patients']:
        writer.writerow({k: p.get(k, '') for k in fieldnames})
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), 
                     mimetype='text/csv', 
                     as_attachment=True, 
                     download_name=f'patients_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')

# DÉMO ET RÉINITIALISATION
@app.route('/api/demo/init', methods=['POST'])
def init_demo_data():
    demo_patients = [
        {'nom': 'Jean Dupont', 'age': 65, 'sexe': 'Homme', 'taille': 172, 'glycemie': 1.35, 'tension': 'Anormale', 'fumeur': 'Fumeur', 'contact': 'jean@email.com'},
        {'nom': 'Marie Martin', 'age': 42, 'sexe': 'Femme', 'taille': 165, 'glycemie': 1.05, 'tension': 'Normale', 'fumeur': 'Non-fumeur', 'contact': 'marie@email.com'},
        {'nom': 'Pierre Bernard', 'age': 58, 'sexe': 'Homme', 'taille': 180, 'glycemie': 1.20, 'tension': 'Normale', 'fumeur': 'Fumeur', 'contact': 'pierre@email.com'},
        {'nom': 'Sophie Laurent', 'age': 35, 'sexe': 'Femme', 'taille': 160, 'glycemie': 0.95, 'tension': 'Normale', 'fumeur': 'Non-fumeur', 'contact': 'sophie@email.com'},
        {'nom': 'Luc Dubois', 'age': 72, 'sexe': 'Homme', 'taille': 168, 'glycemie': 1.45, 'tension': 'Anormale', 'fumeur': 'Fumeur', 'contact': 'luc@email.com'},
        {'nom': 'Claire Petit', 'age': 28, 'sexe': 'Femme', 'taille': 170, 'glycemie': 0.88, 'tension': 'Normale', 'fumeur': 'Non-fumeur', 'contact': 'claire@email.com'},
        {'nom': 'Thomas Leroy', 'age': 50, 'sexe': 'Homme', 'taille': 175, 'glycemie': 1.15, 'tension': 'Normale', 'fumeur': 'Non-fumeur', 'contact': 'thomas@email.com'},
        {'nom': 'Isabelle Moreau', 'age': 68, 'sexe': 'Femme', 'taille': 158, 'glycemie': 1.30, 'tension': 'Anormale', 'fumeur': 'Non-fumeur', 'contact': 'isabelle@email.com'},
        {'nom': 'Nicolas Lefevre', 'age': 45, 'sexe': 'Homme', 'taille': 182, 'glycemie': 1.08, 'tension': 'Normale', 'fumeur': 'Fumeur', 'contact': 'nicolas@email.com'},
        {'nom': 'Catherine Rousseau', 'age': 55, 'sexe': 'Femme', 'taille': 162, 'glycemie': 1.25, 'tension': 'Anormale', 'fumeur': 'Non-fumeur', 'contact': 'catherine@email.com'},
        {'nom': 'David Mercier', 'age': 33, 'sexe': 'Homme', 'taille': 178, 'glycemie': 0.98, 'tension': 'Normale', 'fumeur': 'Non-fumeur', 'contact': 'david@email.com'},
        {'nom': 'Emilie Fournier', 'age': 62, 'sexe': 'Femme', 'taille': 165, 'glycemie': 1.28, 'tension': 'Normale', 'fumeur': 'Fumeur', 'contact': 'emilie@email.com'},
        {'nom': 'Francois Girard', 'age': 38, 'sexe': 'Homme', 'taille': 175, 'glycemie': 1.02, 'tension': 'Normale', 'fumeur': 'Non-fumeur', 'contact': 'francois@email.com'},
        {'nom': 'Julie Lemoine', 'age': 70, 'sexe': 'Femme', 'taille': 155, 'glycemie': 1.38, 'tension': 'Anormale', 'fumeur': 'Non-fumeur', 'contact': 'julie@email.com'},
        {'nom': 'Alexandre Petit', 'age': 48, 'sexe': 'Homme', 'taille': 185, 'glycemie': 1.12, 'tension': 'Normale', 'fumeur': 'Fumeur', 'contact': 'alexandre@email.com'}
    ]
    
    data = {'patients': []}
    for i, p in enumerate(demo_patients):
        p['id'] = i + 1
        p['niveau_risque'] = calculer_niveau_risque(p['age'], p['glycemie'], p['tension'], p['fumeur'], p['taille'])
        p['date_creation'] = datetime.now().isoformat()
        data['patients'].append(p)
    save_data(data)
    return jsonify({'message': 'Données démo chargées (15 patients)'})

@app.route('/api/reset', methods=['POST'])
def reset_data():
    save_data({'patients': []})
    return jsonify({'message': 'Données réinitialisées'})

@app.route('/api/health', methods=['GET'])
def health_check():
    data = load_data()
    return jsonify({
        'status': 'OK',
        'patients': len(data['patients'])
    })

if __name__ == '__main__':
    if not os.path.exists(DATA_FILE):
        save_data({'patients': []})
    
    print("\n" + "="*50)
    print("🏥 MediTrack API démarrée")
    print("="*50)
    print(f"📄 Fichier de données: {DATA_FILE}")
    print(f"🌐 Page web: http://localhost:5000")
    print("="*50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
