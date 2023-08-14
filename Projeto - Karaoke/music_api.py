import shutil
import struct
from flask import Flask, request, jsonify
from flask_cors import CORS
from multiprocessing import Process
import uuid
import eyed3
import os
import threading
import socket
import selectors
import json
import tempfile
import time
import errno
from pydub import AudioSegment
import math
import signal
import sys
import struct
import random
from collections import OrderedDict
import datetime
import time
from flask import url_for,send_from_directory
workers = []
workers_ordem ={}
diretorio_api = tempfile.TemporaryDirectory()
lista_instrumentos=[]
job_queue = OrderedDict()
workers_busy = False
jobs = {}
workers_time = {}
bytes_recebidos = 0
tic = 0
toc = 0
music_working = {}
bytes_do_ficheiro = 0

class SocketServer:
    def __init__(self):
        self.sel = selectors.DefaultSelector()
        self.host = 'localhost'
        self.port = 12000
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen()
        self.num_ficheiros_receber = 0
        self.recebidos = 0
        self.conn_count = 0

        print(f"Listening on {self.host}:{self.port}")
        self.sock.setblocking(False)
        self.sel.register(self.sock, selectors.EVENT_READ, self.accept)
        self.running = True

    def accept(self, sock, mask):
        conn, addr = sock.accept()
        print(f"Accepted connection from {addr}")
        conn.setblocking(False)
        workers.append(conn)
        self.sel.register(conn, selectors.EVENT_READ, self.receive_audio_file)




    def send_audio_file(self,conn, music_id, file_path,job_id):
        """Send music_id and audio file to client over socket."""
        global bytes_do_ficheiro
        self.num_ficheiros_receber=len(workers) * len(lista_instrumentos)
        # Open file for reading in binary mode
        with open(file_path, 'rb') as f:
            """Send reset message to client over socket."""
            reset_message = "Reset:False"
            # Convert reset message string to a 4-byte string in network byte order
            reset_message_prefix = struct.pack('!I', len(reset_message.encode()))
            # Send reset message prefix and reset message to client
            conn.sendall(reset_message_prefix + reset_message.encode())

            # Get size of file in bytes
            file_size = os.path.getsize(file_path)
            # Convert to 4-byte string in network byte order
            size_prefix = struct.pack('!I', file_size)
            # Serialize music_id to a JSON string
            music_data = json.dumps({'music_id': music_id,'track_list':lista_instrumentos,'job_id':job_id})
            # Convert music_id string to a 4-byte string in network byte order
            music_id_prefix = struct.pack('!I', len(music_data.encode()))
            # Send size prefix and music_id prefix to client
            conn.sendall(size_prefix + music_id_prefix)
            # Send music_id string to client
            conn.sendall(music_data.encode())

            # Read and send the file in chunks
            while True:
                # Read a chunk of data from the file
                data = f.read(1024)
                if not data:
                    # All data has been sent
                    break
                while data:
                    try:
                        # Send the chunk of data
                        sent = conn.send(data)
                        # Remove sent data from the chunk
                        data = data[sent:]
                    except socket.error as e:
                        # Handle any socket errors
                        if e.errno == errno.EAGAIN or e.errno == errno.EWOULDBLOCK:
                            # Resource temporarily unavailable, wait and retry
                            time.sleep(0.1)
                            continue
                        else:
                            print("Error sending data:", str(e))
                            break

    def send_reset_message(self,conn):
        """Send reset message to client over socket."""
        reset_message = "Reset:True"
        # Convert reset message string to a 4-byte string in network byte order
        reset_message_prefix = struct.pack('!I', len(reset_message.encode()))
        # Send reset message prefix and reset message to client
        conn.sendall(reset_message_prefix + reset_message.encode())

    def receive_audio_file(self, conn, mask):
        """Callback for receiving audio."""
        global workers_busy
        print("Receiving audio")

        # Receive size prefix from client
        size_prefix = b""
            
        while len(size_prefix) < 4:
            try:
                data = conn.recv(4 - len(size_prefix))
            except BlockingIOError as e:
                if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                    print("Error receiving size prefix:", str(e))
                continue


            if not data:
                print("Worker disconnect")
                workers.remove(conn)
                self.sel.unregister(conn)
                conn.close()
                return None
            size_prefix += data

        if len(size_prefix) == 4:
            # Convert size prefix from 4-byte string in network byte order to integer
            file_size = struct.unpack('!I', size_prefix)[0]

            # Receive music_id prefix from server
            id_prefix = b""
            while len(id_prefix) < 4:
                try:
                    data = conn.recv(4 - len(id_prefix))
                except BlockingIOError as e:
                    if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                        print("Error receiving music_id prefix:", str(e))
                    continue
                if not data:
                    break
                id_prefix += data

            if len(id_prefix) == 4:
                # Convert music_id prefix from 4-byte string in network byte order to integer
                id_size = struct.unpack('!I', id_prefix)[0]
                # Receive music_id string from server
                music_id_dic = b""
                while len(music_id_dic) < id_size:
                    try:
                        data = conn.recv(id_size - len(music_id_dic))
                    except BlockingIOError as e:
                        if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                            print("Error receiving music_id string:", str(e))
                        continue
                    if not data:
                        break
                    music_id_dic += data

                if len(music_id_dic) == id_size:
                    music_id_dic = music_id_dic.decode('ascii')
                    music_id_dic = json.loads(music_id_dic)
                    music_id = music_id_dic['music_id']
                    filename = music_id_dic['filename']
                    job_id = music_id_dic['job_id']
                    os.makedirs(diretorio_api.name+f'/Recebido_{music_id}/{workers_ordem[conn]}/',exist_ok=True)
                    print(workers_ordem[conn])
                    with open(os.path.join(diretorio_api.name+f'/Recebido_{music_id}/{workers_ordem[conn]}/', f'{filename}'), "wb") as f:
                        bytes_received = 0
                        while bytes_received < file_size:
                            # Receive 1024 bytes from server or less if remaining bytes is less than 1024
                            remaining_bytes = file_size - bytes_received
                            try:
                                data = conn.recv(min(1024, remaining_bytes))
                            except BlockingIOError as e:
                                if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                                    print("Error receiving audio data:", str(e))
                                continue
                            if not data:
                                #Verificar se o conn é o ultimo das keys do dicionario
                                break
                            bytes_received += len(data)
                            f.write(data)

                    # Check if all bytes have been received
                    if bytes_received == file_size:
                        self.conn_count += 1
                        if self.conn_count == len(lista_instrumentos):  #garante que recebeu tudo do conn.            
                            global worker_times
                            finish_time = datetime.datetime.now()
                            worker_times[conn][1] = finish_time
                            time_difference = (worker_times[conn][1] - worker_times[conn][0]).total_seconds()
                            worker_times[conn][2] = time_difference
                            global bytes_recebidos
                            bytes_recebidos = bytes_received
                            criar_ficheiro_tempo(f'{diretorio_api.name}/tempos.txt',conn)
                            self.conn_count = 0
                            socket_server.update_jobs(job_id,file_size,music_id)
                        
                        
                        self.recebidos+=1
                        print("Audio received")
                        if self.recebidos == self.num_ficheiros_receber:
                            print("Tudo recebido !!!")
                            self.recebidos = 0
                            self.num_ficheiros_receber = 0
                            self.conn_count = 0
                            #Verifica se music_working está vazio
                            if not music_working:
                                clear_files(diretorio_api.name)
                                return None
                            
                            status,instruments = music_working[music_id]
                            music_working[music_id] = ("DONE",instruments)
                            overlay_mp3(diretorio_api.name+f'/Recebido_{music_id}/',lista_instrumentos,music_id)
                            process_next_job()
                    else:
                        print("Incomplete audio received")
                else:
                    print("Error receiving music_id string")
            else:
                print("Error receiving music_id prefix")
        else:
            print("Error receiving size prefix")

    def update_jobs(self,job_id,bytes_recebidos,music_id):
        global jobs
        toc = time.perf_counter()
        tempo = toc - tic
        jobs[job_id].append("bytes:"+str(bytes_recebidos))
        jobs[job_id].append("tempo:"+str(tempo))
        jobs[job_id].append("music_id:"+str(music_id))


    
    def signal_handler(self,sig, frame):
        print('You pressed Ctrl+C!')
        self.sock.close()
        self.sel.unregister(self.sock)
        self.sel.close()
        sys.exit(0)

    def stop(self):
        # Definir a flag de execução como False para parar o loop
        self.running = False
        # Fechar o socket
        self.sock.close()
        # Remover o socket do seletor
        if self.sock.fileno() != -1:
            self.sel.unregister(self.sock)
        # Parar o loop
        self.sel.close()
        sys.exit()

    def loop(self):
        """Loop indefinetely."""
        while True:
            print("----Server is listening----")
            events = self.sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
    




app = Flask(__name__)
CORS(app)


# Lista vazia para armazenar as músicas submetidas
music_list = []
instrument_tracks = [{"name": "bass","track_id": 1},{"name": "drums","track_id": 2},{"name": "vocals","track_id": 3},{"name": "other","track_id": 4}]

@app.route('/music', methods=['POST'])
def add_music():
    
    # Recebe o arquivo de áudio em formato MP3 enviado na requisição
    audio_file = request.files.get('audio')
    music_id = str(uuid.uuid4())  # cria um identificador único para a música
    instrument_tracks = [{"name": "bass","track_id": 1},{"name": "drums","track_id": 2},{"name": "vocals","track_id": 3},{"name": "other","track_id": 4}]

    # Salva o arquivo no disco com o nome igual ao music_id
    response_data = save_file(audio_file, audio_file.filename, music_id, instrument_tracks)
    
    print(response_data)
    return jsonify(response_data)


def save_file(file, filename,music_id, instrument_tracks):
    file.save(diretorio_api.name+f'/{music_id}')
    temp_file = os.path.join(diretorio_api.name+f'/{music_id}')
    audio = eyed3.load(temp_file)
    if audio.tag:
        name = audio.tag.title
        band = audio.tag.artist
    else:
        name = ""
        band = ""
    response_data = create_json(music_id, name, band, instrument_tracks)
    music_list.append({music_id:filename})
    music_working[music_id] = ("Waiting",instrument_tracks)
    return response_data

def create_json(music_id, name, band, tracks):
    data = {
        "music_id": music_id,
        "name": name,
        "band": band,
        "tracks": tracks
    }
    return data


@app.route('/music', methods=['GET'])
def get_music_list():
    response_data = []
    for music in music_list:
        music_id = list(music.keys())[0]
        path = diretorio_api.name+f'/{music_id}'
        print(str(path))
        temp_file = os.path.join(diretorio_api.name+f'/{music_id}')
        audio = eyed3.load(temp_file)
        if audio.tag:
            name = audio.tag.title
            band = audio.tag.artist
        else:
            name = ""
            band = ""
        response_data.append(create_json(music_id, name, band, instrument_tracks))
    return jsonify(response_data)



def add_job_to_queue(music_id,instrument_tracks_to_keep):
    """Add a job to the queue."""
    job_queue[music_id] = (instrument_tracks_to_keep)

def process_next_job():
    """Process the next job in the queue."""
    global workers_busy
    global lista_instrumentos
    if job_queue:
        music_id, (instrument_tracks_to_keep) = job_queue.popitem(last=False)  # Remove and return the first item in the queue   
        # Process the job here
        print(f"Processing job for music {music_id} with instrument tracks: {instrument_tracks_to_keep}")
        # Mark workers as busy
        workers_busy = True
        music_id = str(music_id)
        lista_instrumentos = []
        lista_instrumentos_sem_numeracao = instrument_tracks_to_keep
        for item in instrument_tracks:
            if item['name'] in lista_instrumentos_sem_numeracao:
                lista_instrumentos.append(item)

        send_music_to_workers(music_id,lista_instrumentos_sem_numeracao)
    else:
        # No jobs in the queue, mark workers as available
        lista_instrumentos.clear()
        workers_busy = False


@app.route('/music/<music_id>', methods=['POST'])
def process_music(music_id):
    global workers_busy
    # Recebe o arquivo JSON com a lista de identificadores das pistas de instrumentos a serem mantidas na música final
    instrument_tracks_to_keep = request.get_json().get('instrument_tracks_to_keep')

    if workers_busy:
        # Workers are currently busy, add the job to the queue
        add_job_to_queue(music_id,instrument_tracks_to_keep)
        return jsonify({'success': 'Música adicionada à fila'}), 200

    # Procura a música correspondente ao music_id

    for music in music_list:
        if music_id in music.keys():
            for instrumento in instrument_tracks_to_keep:
                for dicionario in instrument_tracks:
                    if dicionario["name"] == instrumento:
                        lista_instrumentos.append(dicionario)
            # Mark workers as busy
            workers_busy = True
            # Envio da música para os workers
            if len(workers) == 0:
                workers_busy = False
                return jsonify({'error': 'Não existem workers disponíveis'}), 404
            else:
                send_music_to_workers(music_id,instrument_tracks_to_keep)
                return jsonify({'success': 'Música encontrada'}), 200
    
    return jsonify({'error': 'Música não encontrada'}), 404



def send_music_to_workers(music_id,instrument_tracks_to_keep):
    """Send music to the workers for processing."""
    global worker_times,tic,bytes_do_ficheiro
    start_time = datetime.datetime.now()
    worker_times = {worker: [start_time, None,None] for worker in workers}

    #timer
    tic = time.perf_counter()

    music_working[music_id] = ("Working",instrument_tracks_to_keep)

    bytes_do_ficheiro = os.path.getsize(diretorio_api.name + '/' + str(music_id))
    
    if len(workers) > 1:
        # Split the music into parts
        divisoes = create_music_directory(music_id)
        split_mp3(diretorio_api.name + '/' + music_id, divisoes, len(workers))
        for i in range(len(workers)):
            job_id = gerar_job_id()
            while job_id in jobs:
                job_id = gerar_job_id()
            
            jobs[job_id] = []
            workers_ordem[workers[i]] = i
            SocketServer.send_audio_file(socket_server, workers[i], str(music_id), divisoes + '/' + 'part_' + str(i) + '.mp3', job_id)
    else:
        for i in range(len(workers)):
            job_id = gerar_job_id()
            while job_id in jobs:
                job_id = gerar_job_id()
            
            jobs[job_id] = []
            workers_ordem[workers[i]] = i
            SocketServer.send_audio_file(socket_server, workers[i], str(music_id), diretorio_api.name + '/' + str(music_id), job_id)



def create_music_directory(music_id):
    """Cria um diretório para as divisões da música ou retorna-o se já existir."""
    divisoes = diretorio_api.name + f'/Divisões_{music_id}'
    if not os.path.exists(divisoes):
        os.mkdir(divisoes)
    return divisoes




def gerar_job_id():
    numero = random.randint(1000000, 9999999)
    while numero in jobs.keys():
        numero = random.randint(1000000, 9999999)
    return int(numero)


def criar_ficheiro_tempo(file_path,conn):
    try:
        if os.path.isfile(file_path):
            with open(file_path, 'a') as file:
                file.write("Bytes: "+str(bytes_do_ficheiro) + " Tempo(s): "+ str(worker_times[conn][2])+ " Byte/Sec: "+ str(bytes_do_ficheiro/worker_times[conn][2]) +"\n")
        else:
            with open(file_path, 'w') as file:
                file.write("Bytes: "+str(bytes_do_ficheiro) + " Tempo(s): "+ str(worker_times[conn][2])+ " Byte/Sec: "+ str(bytes_do_ficheiro/worker_times[conn][2]) +"\n")

        print(f"Time log file created/updated: {file_path}")
    except IOError:
        print("Error creating/updating the time log file")




def split_mp3(file_path, output_directory, num_parts):
    # Carregar o arquivo MP3
    audio = AudioSegment.from_file(file_path, format='mp3')

    # Calcular a duração de cada parte em milissegundos
    duration = len(audio)
    part_duration = math.ceil(duration / num_parts)

    # Dividir o arquivo em partes iguais
    for i in range(num_parts):
        # Calcular o índice inicial e final para cada parte
        start_index = i * part_duration
        end_index = start_index + part_duration

        # Obter o segmento de áudio correspondente à parte atual
        part = audio[start_index:end_index]

        # Definir o nome do arquivo de saída para cada parte
        output_file = os.path.join(output_directory, f'part_{i}.mp3')

        # Salvar a parte como um novo arquivo MP3
        part.export(output_file, format='mp3')

        print(f'Part {i} saved.')

    print('Splitting complete.')

def overlay_mp3(input_directory,lista_instrumentos,music_id):
    # Percorrer todas as pastas e arquivos dentro do diretório de entrada
    for item in lista_instrumentos:
        print(item)
    for root, dirs, files in os.walk(input_directory):
        overlayed_audio = None  # Inicializar o áudio resultante como None

        for file in files:
            for item in lista_instrumentos:
                if file.endswith(".wav") and file[:-4] == item["name"]:
                    file_path = os.path.join(root, file)
                    # Carregar o segmento de áudio do arquivo
                    audio = AudioSegment.from_wav(file_path)

                    if overlayed_audio is None:
                        # Inicializar o áudio resultante com o primeiro arquivo
                        overlayed_audio = audio
                    else:
                        # Sobrepor o áudio ao áudio resultante atual
                        overlayed_audio = overlayed_audio.overlay(audio)

        if overlayed_audio is not None:
            # Salvar o arquivo sobreposto na mesma pasta
            output_file = os.path.join(root, "overlayed.wav")
            overlayed_audio.export(output_file, format='wav')
            print(f"Áudios sobrepostos em: {output_file}")
        else:
            print(f"Nenhum arquivo WAV encontrado para sobreposição na pasta: {root}")
    merge_overlayed_wav_files(input_directory, input_directory + f"final_{music_id}.mp3")
    merge_all_wav_files(input_directory,music_id,lista_instrumentos)

def merge_overlayed_wav_files(input_directory, output_file):
    audio_segments = []  # Lista para armazenar os segmentos de áudio

    # Percorrer as pastas numeradas no diretório de entrada
    for folder_name in sorted(os.listdir(input_directory)):
        folder_path = os.path.join(input_directory, folder_name)

        if os.path.isdir(folder_path):
            # Verificar se existe o arquivo "overlayed.wav" na pasta
            overlayed_wav_file = os.path.join(folder_path, "overlayed.wav")

            if os.path.isfile(overlayed_wav_file):
                # Carregar o segmento de áudio do arquivo "overlayed.wav"
                audio_segment = AudioSegment.from_wav(overlayed_wav_file)

                # Adicionar o segmento de áudio à lista
                audio_segments.append(audio_segment)

    if len(audio_segments) > 0:
        # Juntar os segmentos de áudio em um único segmento
        merged_audio = audio_segments[0]
        for audio_segment in audio_segments[1:]:
            merged_audio += audio_segment

        # Salvar o arquivo WAV final
        merged_audio.export(output_file, format='mp3')
        print(f"Arquivos overlayed.wav mesclados em: {output_file}")
    else:
        print("Nenhum arquivo overlayed.wav encontrado para mesclagem.")

def merge_all_wav_files(input_directory, music_id,lista_instrumentos):
    drums_segments = []  # Lista para armazenar os segmentos de áudio
    vocals_segments = []
    other_segments = []
    bass_segments = []

    # Percorrer as pastas numeradas no diretório de entrada
    for item in lista_instrumentos:
        for folder_name in sorted(os.listdir(input_directory)):
            folder_path = os.path.join(input_directory, folder_name)

            if os.path.isdir(folder_path):
                if (item['name'] == 'drums'):
                    drums_wav_file = os.path.join(folder_path, "drums.wav")
                # Verificar se existe o arquivo "overlayed.wav" na pasta
                if (item['name'] == 'vocals'):
                    vocals_wav_file = os.path.join(folder_path, "vocals.wav")
                if(item['name'] == 'other'):
                    other_wav_file = os.path.join(folder_path, "other.wav")
                if(item['name'] == 'bass'): 
                    bass_wav_file = os.path.join(folder_path, "bass.wav")

                if item['name'] == 'drums' and os.path.isfile(drums_wav_file):
                    # Carregar o segmento de áudio do arquivo "overlayed.wav"
                    drums_segment = AudioSegment.from_wav(drums_wav_file)

                    # Adicionar o segmento de áudio à lista
                    drums_segments.append(drums_segment)
                if item['name'] == 'vocals' and os.path.isfile(vocals_wav_file):
                    # Carregar o segmento de áudio do arquivo "overlayed.wav"
                    vocals_segment = AudioSegment.from_wav(vocals_wav_file)

                    # Adicionar o segmento de áudio à lista
                    vocals_segments.append(vocals_segment)
                if item['name'] == 'other' and os.path.isfile(other_wav_file):
                    # Carregar o segmento de áudio do arquivo "overlayed.wav"
                    other_segment = AudioSegment.from_wav(other_wav_file)

                    # Adicionar o segmento de áudio à lista
                    other_segments.append(other_segment)
                if item['name'] == 'bass' and os.path.isfile(bass_wav_file):
                    # Carregar o segmento de áudio do arquivo "overlayed.wav"
                    bass_segment = AudioSegment.from_wav(bass_wav_file)

                    # Adicionar o segmento de áudio à lista
                    bass_segments.append(bass_segment)

    if len(drums_segments) > 0:
        # Juntar os segmentos de áudio em um único segmento
        merged_audio = drums_segments[0]
        for audio_segment in drums_segments[1:]:
            merged_audio += audio_segment

        # Salvar o arquivo WAV final
        merged_audio.export(input_directory + f'drums_{music_id}.mp3', format='mp3')

    if len(vocals_segments) > 0:
        # Juntar os segmentos de áudio em um único segmento
        merged_audio = vocals_segments[0]
        for audio_segment in vocals_segments[1:]:
            merged_audio += audio_segment

        # Salvar o arquivo WAV final
        merged_audio.export(input_directory + f'vocals_{music_id}.mp3', format='mp3')

    if len(other_segments) > 0:
        # Juntar os segmentos de áudio em um único segmento
        merged_audio = other_segments[0]
        for audio_segment in other_segments[1:]:
            merged_audio += audio_segment

        # Salvar o arquivo WAV final
        merged_audio.export(input_directory + f'other_{music_id}.mp3', format='mp3')
    if len(bass_segments) > 0:
        # Juntar os segmentos de áudio em um único segmento
        merged_audio = bass_segments[0]
        for audio_segment in bass_segments[1:]:
            merged_audio += audio_segment

        # Salvar o arquivo WAV final
        merged_audio.export(input_directory + f'bass_{music_id}.mp3', format='mp3')


@app.route('/music/<music_id>', methods=['GET'])
def get_process(music_id):
    global toc,music_working,bytes_do_ficheiro
    toc = time.perf_counter()
    progresso = 0
    if music_id not in music_working.keys():
        return jsonify({"error": "Música não foi encontrada"}), 404
    elif music_working[music_id][0] == "Waiting":
        return jsonify({"error": "Música ainda não foi processada"}), 404
    
    
    
    elif music_working[music_id][0] == "DONE":
        diretorio_das_musicas = diretorio_api.name + f'/Recebido_{music_id}/'
        lista_tracks = []
        for instrumento in music_working[music_id][1]:
            for arquivo in os.listdir(diretorio_das_musicas):
                if arquivo.startswith(instrumento):
                    link_arquivo = url_for('download', music_id=music_id, instrumento=instrumento, _external=True)
                    lista_tracks.append({"name": instrumento, "track": link_arquivo})

        track_final = url_for('download', music_id=music_id, instrumento='final', _external=True)
        data = {
            "progress": 100,
            "instruments": lista_tracks,
            "final": track_final
        }
        return jsonify(data), 200
    else:
        tempo_atual = toc-tic 
        txtmedia = f'{diretorio_api.name}/tempos.txt'

        if not os.path.isfile(txtmedia):
            with open(f'{diretorio_api.name}/tempos.txt', 'w') as f:
                f.write("Bytes: "+ "Default" + " Tempo(s): "+ "Default" + " Byte/Sec: " + "40000" +"\n")
        media = calcular_media_byte_sec(txtmedia)
        progresso = tempo_atual * media / bytes_do_ficheiro * 100
        if(progresso >= 100):
            progresso = 100 
        data = {
            "progress": progresso}
        progresso = 0
        return jsonify(data), 200


@app.route('/download/<string:music_id>/<instrumento>', methods=['GET'])
def download(music_id, instrumento):
    global diretorio_api

    diretorio_das_musicas = f'{diretorio_api.name}/Recebido_{music_id}'

    if instrumento == 'final':
        filename = f'final_{music_id}.mp3'
    else:
        filename = f'{instrumento}_{music_id}.mp3'

    return send_from_directory(diretorio_das_musicas, filename, as_attachment=True)



def calcular_media_byte_sec(arquivo):
    with open(arquivo, 'r') as file:
        lines = file.readlines()
    
    byte_sec_values = []
    for line in lines:
        if 'Byte/Sec' in line:
            byte_sec = line.split('Byte/Sec:')[1].strip()
            byte_sec_values.append(float(byte_sec))
    
    if len(byte_sec_values) == 0:
        return None
    
    media = sum(byte_sec_values) / len(byte_sec_values)
    return media

@app.route('/job', methods=['GET'])
def get_job_list():
    lista_jobs = []
    for job in jobs.keys():
        lista_jobs.append(job)
    return jsonify(lista_jobs), 200


@app.route('/job/<job_id>', methods=['GET'])
def get_job(job_id):
    for job in jobs.keys():
        if int(job) == int(job_id):
            if jobs[job] == []:
                return jsonify({"error": "Job ainda não foi processado"}), 404
            return jsonify(jobs[job]), 200
    return jsonify({"error": "Job não encontrado"}), 404

@app.route('/reset', methods=['POST'])
def reset():
    # Percorre todos os arquivos e subdiretórios dentro do diretório
    clear_files(diretorio_api.name)
    #Volta as variaveis para o estado inicial
    jobs.clear()
    music_working.clear()
    music_list.clear()
    lista_instrumentos.clear()
    global workers_busy
    workers_busy = False
    for worker in workers:
        socket_server.send_reset_message(worker)
    return jsonify({"success": "Reset realizado com sucesso"}), 200

def clear_files(path1):
    # Percorre todos os arquivos e subdiretórios dentro do diretório
    for filename in os.listdir(path1):
        file_path = os.path.join(path1, filename)
        if os.path.isfile(file_path):
            # Remove o arquivo
            os.remove(file_path)
        elif os.path.isdir(file_path):
            # Remove o diretório e todo o seu conteúdo
            shutil.rmtree(file_path)



def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    diretorio_api.cleanup()
    # Encerrar a thread do socket listener
    socket_server.stop()
    socket_thread.join()
    socket_thread.stop()
    sys.exit(0)




# Inicia a thread do socket listener
socket_server = SocketServer()
socket_thread = threading.Thread(target=socket_server.loop)
socket_thread.start()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.run(debug=False)


