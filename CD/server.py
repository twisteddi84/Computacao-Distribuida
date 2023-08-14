import socket
import threading

port = 12000
ip = 'localhost'
server = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
server.bind((ip, port))
server.listen()
clients = []
usernames = []

def all_clients(message):
    for client in clients:
        client.send(message)

def client_connection(client):
    while True:
        try:
            message = client.recv(1024)
            all_clients(message)
        except:
            index = clients.index(client)
            clients.remove(client)
            client.close()
            username = usernames[index]
            all_clients("{} abandonou o chat.".format(username).encode('utf-8'))
            usernames.remove(username)
            break

def listenning():
    while True:
        print("----Server is listening----")
        client, address = server.accept()
        print("Connection succesfully made with {}".format(str(address)))
        client.send("Username:".encode('utf-8'))
        username = client.recv(1024)
        clients.append(client)
        usernames.append(username)
        print("Your username is {}".format(username).encode('utf-8'))
        all_clients("Welcome {}.".format(username).encode('utf-8'))
        client.send("You are connected.".encode('utf-8'))
        thread = threading.Thread(target= client_connection, args=(client,))
        thread.start()

def main():
    listenning()

main()