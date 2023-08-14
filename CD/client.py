import threading
import socket

port = 12000
ip = 'localhost'
username = input("Your Username:")
client = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
client.connect((ip,port))

def receive_message():
    while True:
        try:
            message = client.recv(1024).decode('utf-8')
            if message=="Username:":
                client.send(username.encode('utf-8'))
            else:
                print(message)
        except:
            print("Error!!")
            client.close()
            break

def send_message():
    while True:
        message = "{}: {}".format(username,input(""))
        client.send(message.encode('utf-8'))

def main():
    thread_receive = threading.Thread(target=receive_message)
    thread_send = threading.Thread(target=send_message)
    thread_receive.start()
    thread_send.start()

main()