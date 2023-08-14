"""CD Chat server program."""
import json
import logging
import selectors
import socket
from .protocol import CDProto, CDProtoBadFormat,RegisterMessage
logging.basicConfig(filename="server.log", level=logging.DEBUG)

class Server:
    """Chat Server process."""

    def __init__(self):
        """Initializes chat client."""
        self.ip = 'localhost'
        self.port = 12000
        self.socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.socket.bind((self.ip, self.port))
        self.socket.listen()
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.socket, selectors.EVENT_READ, self.accept)

        self.dict_conn={}  #{conn:[username,channel]}

        pass

    def accept(self,socket,mask):
        conn, address = socket.accept()  # Should be ready

        username = CDProto.recv_msg(conn)
        username_dict = json.loads(username.string)
        username_str = username_dict["user"]
        print("Connection successfully made with {}".format(str(address)))
        self.dict_conn[conn] = [username_str,None]
        print("{}, welcome to channel {}".format(self.dict_conn[conn][0],self.dict_conn[conn][1]))

        conn.setblocking(False)
        self.sel.register(conn, selectors.EVENT_READ, self.read)

    def read(self,conn,mask):
        try:
            data = CDProto.recv_msg(conn)
            if data:
                data_dict = json.loads(data.string)
                print(data_dict)
                if data_dict["command"]=="message":
                    if data_dict["message"] == "exit":
                        self.dict_conn.pop(conn)
                        self.sel.unregister(conn)
                        conn.close()
                    else:
                        if("channel" in data_dict.keys()):
                            for key in self.dict_conn.keys():
                                if (self.dict_conn[key][1] == data_dict["channel"]):
                                    message = CDProto.message(data_dict["message"],data_dict["channel"])
                                    CDProto.send_msg(key,message)
                        else:
                            for key in self.dict_conn.keys():
                                if (self.dict_conn[key][1] == None):
                                    print("OLAAAA")
                                    message = CDProto.message(data_dict["message"],None)
                                    CDProto.send_msg(key,message)
                if data_dict["command"] == "join":
                    new_channel = data_dict["channel"]
                    self.dict_conn[conn][1] = new_channel
                    print(self.dict_conn[conn][1])
                    for key in self.dict_conn.keys():
                        if (self.dict_conn[key][1] == new_channel):
                            string_ = "Joined {}".format(new_channel)
                            message = CDProto.message(string_,new_channel)
                            CDProto.send_msg(key,message)
            else:
                self.dict_conn.pop(conn)
                self.sel.unregister(conn)
                conn.close()
                return
        except socket.error as e:
            print("Error receiving data:", e)
            self.sel.unregister(conn)
            conn.close()




    def loop(self):
        """Loop indefinetely."""
        while True:
            print("----Server is listening----")
            events = self.sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
