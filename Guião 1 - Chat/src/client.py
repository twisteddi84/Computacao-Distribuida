"""CD Chat client program"""
import json
import logging
import sys
import socket
import selectors
import fcntl
import os
from .protocol import CDProto, CDProtoBadFormat, RegisterMessage

logging.basicConfig(filename=f"{sys.argv[0]}.log", level=logging.DEBUG)


class Client:
    """Chat Client process."""

    def __init__(self, name: str = "Foo"):
        """Initializes chat client."""
        self.username = name
        self.ip = 'localhost'
        self.port = 12000
        self.socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.channel = None
        self.sel=selectors.DefaultSelector()
        pass

    def connect(self):
        """Connect to chat server and setup stdin flags."""
        self.socket.connect((self.ip,self.port))
        self.sel.register(self.socket, selectors.EVENT_READ, self.receive_message)
        register = CDProto.register(self.username)
        CDProto.send_msg(self.socket,register)

    def receive_message(self,socket,mask):
        try:
            message = CDProto.recv_msg(socket)
            message_dict = json.loads(message.string)
            message_string = message_dict["message"].rstrip('\n')
            print("{}:{}".format("Recebida",message_string))
        except Exception as e:
            print(e)
            self.socket.close()
        pass

    def send_message(self,stdin,mask):
        data = str(stdin.read())
        data = data.rstrip("\n")
        if data != "":
            if data.startswith("/join "):
                print("JOINNNNN")
                new_channel = data.replace("/join ","").strip()
                message = CDProto.join(new_channel)
                self.channel = new_channel
                CDProto.send_msg(self.socket, message)
            elif data == "exit":
                data = data.rstrip("\n")
                message = CDProto.message(data, self.channel)
                CDProto.send_msg(self.socket, message)
                self.socket.close()
                sys.exit()
            else:
                message = CDProto.message(data,self.channel)
                CDProto.send_msg(self.socket,message)


    def loop(self):
        """Loop indefinetely."""
        orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)
        self.sel.register(sys.stdin, selectors.EVENT_READ, self.send_message)
        while True:
            sys.stdout.write(">>")
            sys.stdout.flush()
            events = self.sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
        pass
