from flask import Flask, send_file, render_template_string
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string('''
        <h2>Télécharger les données des pharmacies de garde</h2>
        <a href="/download" style="font-size:20px;padding:10px 20px;background:#4CAF50;color:white;text-decoration:none;border-radius:5px;">Télécharger data1.json</a>
    ''')

@app.route('/download')
def download():
    file_path = 'data1.json'
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return 'Fichier non trouvé', 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
