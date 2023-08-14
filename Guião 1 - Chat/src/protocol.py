"""Protocol for chat server - Computação Distribuida Assignment 1."""
import json
from datetime import datetime
from socket import socket


class Message:
    """Message Type."""
    def __init__(self,command):
        self.command = command
        dict_ = {"command": self.command}
        self.string = json.dumps(dict_)
    def __repr__(self):
        dict_ = {"command":self.command}
        return json.dumps(dict_)
    
class JoinMessage(Message):
    """Message to join a chat channel."""
    def __init__(self,command,channel):
        self.channel = channel
        super().__init__(command)
        dict_ = {"command": self.command, "channel": self.channel}
        self.string = json.dumps(dict_)
    def __repr__(self):
        dict_ = {"command": self.command, "channel": self.channel}
        return json.dumps(dict_)



class RegisterMessage(Message):
    """Message to register username in the server."""
    def __init__(self,command,user):
        self.user = user
        super().__init__(command)
        dict_ = {"command": self.command, "user": self.user}
        self.string = json.dumps(dict_)

    def __repr__(self):
        dict_ = {"command":self.command,"user":self.user}
        return json.dumps(dict_)


class TextMessage(Message):
    """Message to chat with other clients."""
    def __init__(self,command,message,ts,channel=None):
        super().__init__(command)
        self.message = message
        self.channel = channel
        self.ts = ts
        if self.channel == None:
            dict_ = {"command": self.command, "message": self.message,"ts":self.ts}
            self.string = json.dumps(dict_)
        else:
            dict_ = {"command": self.command, "message": self.message,"channel":self.channel ,"ts": self.ts}
            self.string = json.dumps(dict_)

    def __repr__(self):
        if self.channel == None:
            dict_ = {"command": self.command, "message": self.message,"ts":self.ts}
            return json.dumps(dict_)
        else:
            dict_ = {"command": self.command, "message": self.message,"channel":self.channel ,"ts": self.ts}
            return json.dumps(dict_)

class CDProto:
    """Computação Distribuida Protocol."""

    @classmethod
    def register(cls, username: str) -> RegisterMessage:
        """Creates a RegisterMessage object."""
        register_message = RegisterMessage("register",username)
        return register_message

    @classmethod
    def join(cls, channel: str) -> JoinMessage:
        """Creates a JoinMessage object."""
        join_message_object = JoinMessage("join", channel)
        return join_message_object


    @classmethod
    def message(cls, message: str, channel: str = None) -> TextMessage:
        """Creates a TextMessage object."""
        text_message_object = TextMessage("message", message, int(datetime.now().timestamp()), channel)
        return text_message_object

    @classmethod
    def send_msg(cls, connection: socket, msg: Message):
        """Sends through a connection a Message object."""
        if type(msg) is JoinMessage:
            string_json = msg.string.encode('utf-8')
            header = len(string_json).to_bytes(2, "big")
            connection.send(header + string_json)
        elif type(msg) is RegisterMessage:
            string_json = msg.string.encode('utf-8')
            header = len(string_json).to_bytes(2, "big")
            connection.send(header + string_json)
        elif type(msg) is TextMessage:
            string_json = msg.string.encode('utf-8')
            header = len(string_json).to_bytes(2, "big")
            connection.send(header + string_json)



    @classmethod
    def recv_msg(cls, connection: socket) -> Message:
        """Receives through a connection a Message object."""
        try:
            header = connection.recv(2)
            msg_size = int.from_bytes(header,byteorder='big')
            if msg_size == 0 :
                return
            message_json = connection.recv(msg_size).decode('utf-8')
            message_dict = json.loads(message_json)
        except json.JSONDecodeError as err:
            raise CDProtoBadFormat(message_json)

        if message_dict["command"] == "register":
            return CDProto.register(message_dict["user"])

        elif message_dict["command"] == "join":
            return CDProto.join(message_dict["channel"])

        elif message_dict["command"] == "message":

            if message_dict.get("channel"):
                return CDProto.message(message_dict["message"], message_dict["channel"])

            else:
                return CDProto.message(message_dict["message"])
        else:
            raise CDProtoBadFormat(message_json)


class CDProtoBadFormat(Exception):
    """Exception when source message is not CDProto."""

    def __init__(self, original_msg: bytes=None) :
        """Store original message that triggered exception."""
        self._original = original_msg

    @property
    def original_msg(self) -> str:
        """Retrieve original message as a string."""
        return self._original.decode("utf-8")
