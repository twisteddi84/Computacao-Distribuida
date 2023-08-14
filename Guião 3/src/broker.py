"""Message Broker"""
import enum
from queue import Empty
from typing import Dict, List, Any, Tuple
import socket, selectors
import json, pickle
import xml.etree.ElementTree as XMLTree

class Serializer(enum.Enum):
    """Possible message serializers."""
    XML = 0
    PICKLE = 1
    JSON = 2

class Broker:
    """Implementation of a PubSub Message Broker."""

    def __init__(self):
        """Initialize broker."""
        self.canceled = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sel = selectors.DefaultSelector()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind( ("localhost", 5003) )
        self.sock.listen(100)

        self.sel.register(self.sock, selectors.EVENT_READ, self.accept)

        self.topic_to_message = {}     # topic : last message 
        self.topic_to_subscribers = {}    # topic : List< (socket, serializer) >
        self.socket_to_serializer = {}    # socket : serializer


    def accept(self, sock, mask):
        conn, addr = sock.accept()
        self.sel.register(conn, selectors.EVENT_READ, self.read)


    def read(self, conn, mask):
        header = int.from_bytes(conn.recv(2), "big")

        if header == 0:
            for topic in self.topic_to_subscribers: 
                self.unsubscribe(topic, conn) 
            self.sel.unregister(conn)
            conn.close()
            return

        msg = conn.recv(header)

        if conn not in self.socket_to_serializer:
            dic_msg = pickle.loads(msg)
        else:
            if self.socket_to_serializer[conn] == Serializer.JSON:
                dic_msg = json.loads(msg)

            elif self.socket_to_serializer[conn] == Serializer.PICKLE:
                dic_msg = pickle.loads(msg)

            elif self.socket_to_serializer[conn] == Serializer.XML:
                tree = XMLTree.fromstring(msg)
                dic = {}
                for child in tree:
                    dic[child.tag] = child.attrib["value"]
                dic_msg = dic
            else:
                dic_msg = None

        if dic_msg:
            command = dic_msg["command"]

            if command == "ser":
                _format = dic_msg["serializer"]

                if _format == "json":
                    self.socket_to_serializer[conn] = Serializer.JSON
                elif _format == "xml":
                    self.socket_to_serializer[conn] = Serializer.XML
                elif _format == "pickle":
                    self.socket_to_serializer[conn] = Serializer.PICKLE

            elif command == "sub":
                topic = dic_msg["topic"]
                _format = self.socket_to_serializer[conn]
                self.subscribe(topic, conn, _format)

            elif command == "pub":
                topic = dic_msg["topic"]
                msg = dic_msg["message"]
                self.topic_to_message[topic] = msg

                for key in list(self.topic_to_subscribers.keys()):
                    if key in topic:
                        for conn in self.topic_to_subscribers[key]:
                            _format = conn[1]
                            _sock = conn[0]
                            dic = {"command": "pub", "topic": topic, "message": msg}
                            self.send(_sock, dic, _format)

            elif command == "list":
                lst = self.list_topics()
                dic = {"command": "list_topics", "topic": None, "message": lst}
                self.send(conn, dic, self.socket_to_serializer[conn])

            elif command == "nmsub":
                topic = dic_msg["topic"]
                self.topic_to_message[topic].remove(conn)

        else:
            conn.close()


    def list_topics(self) -> List[str]:
        """Returns a list of strings containing all topics."""
        return list(self.topic_to_message.keys())


    def get_topic(self, topic):
        """Returns the currently stored value in topic."""
        return self.topic_to_message.get(topic)


    def put_topic(self, topic, value):
        """Store in topic the value."""
        self.topic_to_message[topic] = value


    def list_subscriptions(self, topic: str) -> List[socket.socket]:
        """Provide list of subscribers to a given topic."""
        return self.topic_to_subscribers[topic]


    def subscribe(self, topic: str, address: socket.socket, _format: Serializer = None):
        """Subscribe to topic by client in address."""
        if topic in list(self.topic_to_subscribers.keys()):
            lst = self.topic_to_subscribers[topic]
            lst.append((address, _format))
            self.topic_to_subscribers[topic] = lst
        else:
            self.topic_to_subscribers[topic] = [(address, _format)]

        if topic in list(self.topic_to_message.keys()):
            dic = {"command": "lm", "topic": topic, "message": self.topic_to_message[topic]}
            self.send(address, dic, _format)

        

    def send(self, conn, msg, _format):

        if _format == Serializer.JSON:
            encoded_msg = json.dumps(msg).encode("utf-8")

        elif _format == Serializer.PICKLE:
            encoded_msg = pickle.dumps(msg)

        elif _format == Serializer.XML:
            root = XMLTree.Element('root')

            for key in msg.keys():
                XMLTree.SubElement(root, str(key)).set("value", str(msg[key]))

            encoded_msg = XMLTree.tostring(root)

        header = len(encoded_msg).to_bytes(2, "big")
        conn.send(header + encoded_msg)


    def unsubscribe(self, topic, address):
        """Unsubscribe to topic by client in address."""
        self.topic_to_subscribers[topic] = [sub for sub in self.topic_to_subscribers[topic] if sub[0] != address]


    def run(self):
        """Run until canceled."""
        while not self.canceled:
            events = self.sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
    
