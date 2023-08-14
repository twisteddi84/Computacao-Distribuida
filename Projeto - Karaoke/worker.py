import json
import multiprocessing
import os
import shutil
import socket
import selectors
import logging
import struct
import tempfile
import signal
import sys
import time

from demucs.apply import apply_model
from demucs.pretrained import get_model
from demucs.audio import AudioFile, save_audio

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

diretorio_inicial = tempfile.TemporaryDirectory()

class AudioClient:
    """Audio Client process."""

    def __init__(self, name: str = "Foo"):
        """Initializes audio client."""
        self.username = name
        self.ip = 'localhost'
        self.port = 12000
        self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sel = selectors.DefaultSelector()
        self.job_id = 0
        self.thread = None
        self.process = None

    def connect(self):
        """Connect to audio server."""
        self.socket_server.connect((self.ip, self.port))
        self.sel.register(self.socket_server, selectors.EVENT_READ, self.receive_audio)


    def receive_audio(self, sock, mask):
        """Callback for receiving audio."""
        print("Receiving audio")
        reset_prefix = b""
        while len(reset_prefix) < 4:
            data = sock.recv(4 - len(reset_prefix))
            if not data:
                break
            reset_prefix += data
        if len(reset_prefix) == 4:
            reset_message_size = struct.unpack('!I', reset_prefix)[0]
            reset_message = sock.recv(reset_message_size).decode()

            if reset_message == "Reset:True":
                print("Reset:True")
                self.job_id = 0
                #Vê se o self.process está rodando
                if self.process.is_alive():
                    self.process.kill()
                    
                    print('Parent is continuing on...')
                # Percorre todos os arquivos e subdiretórios dentro do diretório
                if os.path.exists(diretorio_inicial.name):
                    for filename in os.listdir(diretorio_inicial.name):
                        file_path = os.path.join(diretorio_inicial.name, filename)
                        if os.path.isfile(file_path):
                            # Remove o arquivo
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            # Remove o diretório e todo o seu conteúdo
                            shutil.rmtree(file_path)
            else:
                # Receive size prefix from server
                size_prefix = b""
                while len(size_prefix) < 4:
                    data = sock.recv(4 - len(size_prefix))
                    if not data:
                        break
                    size_prefix += data

                if len(size_prefix) == 4:
                    # Convert size prefix from 4-byte string in network byte order to integer
                    file_size = struct.unpack('!I', size_prefix)[0]

                    # Receive music_id prefix from server
                    id_prefix = sock.recv(4)
                    # Convert music_id prefix from 4-byte string in network byte order to integer
                    id_size = struct.unpack('!I', id_prefix)[0]
                    # Receive music_id string from server
                    music_id_dic = sock.recv(id_size).decode('ascii')
                    music_id_dic = json.loads(music_id_dic)
                    music_id = music_id_dic['music_id']
                    lista_instrumentos = music_id_dic['track_list']
                    lista_instrumentos_selecionados = []
                    self.job_id = music_id_dic['job_id']
                    for item in lista_instrumentos:
                        lista_instrumentos_selecionados.append(item['name'])
                    print(diretorio_inicial.name)

                    with open(os.path.join(diretorio_inicial.name, f'{music_id}'), "wb") as f:
                        bytes_received = 0
                        while bytes_received < file_size:
                            # Receive 1024 bytes from server or less if remaining bytes is less than 1024
                            remaining_bytes = file_size - bytes_received
                            data = sock.recv(min(1024, remaining_bytes))
                            # If there is no more data, break out of loop
                            if not data:
                                break
                            bytes_received += len(data)
                            f.write(data)

                    # Check if all bytes have been received
                    if bytes_received == file_size:
                        print("Audio received")
                        # AudioClient.separar_audio(music_id,lista_instrumentos_selecionados)
                        # self.thread = threading.Thread(target=self.separar_audio, args=(music_id,lista_instrumentos_selecionados))
                        # self.thread.start()
                        self.process = multiprocessing.Process(target=self.separar_audio, args=(music_id,lista_instrumentos_selecionados))
                        self.process.start()
                    else:
                        print("Incomplete audio received")
                else:
                    if not size_prefix:
                        print("Server closed connection")
                        diretorio_inicial.cleanup()
                        sys.exit(0)
                    print("Error receiving audio size prefix")


    def separar_audio(self,music_id,lista_instrumentos):
        print("Separando audio")
        model = get_model(name='htdemucs')
        model.cpu()
        model.eval()

        # load the audio file
        wav = AudioFile(diretorio_inicial.name+f'/{music_id}').read(streams=0,
        samplerate=model.samplerate, channels=model.audio_channels)
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()
        
        # apply the model
        sources = apply_model(model, wav[None], device='cpu', progress=True, num_workers=1)[0]
        sources = sources * ref.std() + ref.mean()

        # store the model
        diretorio_destino = diretorio_inicial.name + f'/Divisão_{music_id}'
        if not os.path.exists(diretorio_destino):
            # Criar o diretório se não existir
            os.mkdir(diretorio_destino)
        for source, name in zip(sources, model.sources):
            if name in lista_instrumentos:
                stem = f'{diretorio_destino}/{name}.wav'
                save_audio(source, str(stem), samplerate=model.samplerate)
        print("Separou audio")
        for file in os.listdir(diretorio_destino):
            if file.endswith(".wav"):
                for instrumento in lista_instrumentos:
                    if file.startswith(instrumento):
                        print(file)
                        AudioClient.send_audio(c,diretorio_destino+'/'+file,music_id)

    def send_audio(self, file_path, music_id):
        """Send music_id and audio file to server over socket."""
        # Open file for reading in binary mode
        with open(file_path, 'rb') as f:
            # Get size of file in bytes
            file_size = os.path.getsize(file_path)
            # Convert to 4-byte string in network byte order
            size_prefix = struct.pack('!I', file_size)
            # Serialize music_id and file name to a JSON string
            music_data = {'music_id': music_id, 'filename': os.path.basename(file_path), 'job_id':self.job_id}
            music_data_str = json.dumps(music_data)
            # Convert music_data string to a 4-byte string in network byte order
            music_data_prefix = struct.pack('!I', len(music_data_str.encode()))
            # Send size prefix and music_data prefix to server
            self.socket_server.sendall(size_prefix + music_data_prefix)
            # Send music_data string to server
            self.socket_server.sendall(music_data_str.encode())

            # Read and send the file in chunks
            while True:
                # Read a chunk of data from the file
                data = f.read(1024)
                if not data:
                    # All data has been sent
                    print("Audio sent")
                    break
                # Send the chunk of data
                while data:
                    try:
                        sent = self.socket_server.send(data)
                        data = data[sent:]
                    except BlockingIOError:
                        # Resource temporarily unavailable, wait and retry
                        time.sleep(0.1)
                    except socket.error as e:
                        print("Error sending data:", str(e))
                        break


    

    def signal_handler(self,sig, frame):
        """Disconnect from audio server."""
        print('You pressed Ctrl+C!')
        diretorio_inicial.cleanup()
        self.sel.unregister(self.socket_server)
        self.socket_server.close()
        exit()

    def disconnect(self):
        """Disconnect from audio server."""
        self.sel.unregister(self.socket_server)
        self.socket_server.close()
        exit()

    def loop(self):
        """Loop indefinetely."""
        while True:
            try:
                events = self.sel.select()
            except Exception as e:
                print(f"Error in loop: {e}")
                break
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
    


if __name__ == "__main__":
    c = AudioClient()
    signal.signal(signal.SIGINT, c.signal_handler)
    signal.signal(signal.SIGTERM, c.signal_handler)
    c.connect()
    c.loop()