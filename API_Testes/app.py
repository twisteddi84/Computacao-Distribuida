from flask import Flask, render_template, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # permite todas as origens

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    #Adicionar 'copia' antes do .mp3 no ficheiro 
    file.filename = 'copia_'+file.filename
    file.save('/home/diogofilipe84/Desktop/2º Ano EI/CD/API_Testes/Ficheiros_Recebidos/'+file.filename)
    return f"Thank you"

if __name__ == "__main__":
    app.run()