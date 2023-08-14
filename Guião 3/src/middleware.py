"""Middleware to communicate with PubSub Message Broker."""
from collections.abc import Callable
from enum import Enum
from queue import LifoQueue, Empty
import socket, sys
from typing import Any
import json, pickle
import xml.etree.ElementTree as XMLTree

class MiddlewareType(Enum):
    """Middleware Type."""
    CONSUMER = 1
    PRODUCER = 2


class Queue:
    """Representation of Queue interface for both Consumers and Producers."""

    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        """Create Queue."""
        self.type = _type
        self.topic = topic
        self.sock_middleware = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_middleware.connect( ('localhost', 5003) )


    def push(self, value):
        """Sends data to broker. """
        header = len(value).to_bytes(2, "big")
        self.sock_middleware.send(header + value)


    def pull(self) -> (str, Any):
        """Waits for (topic, data) from broker.
        Should BLOCK the consumer!"""
        message = self.sock_middleware.recv(2)
        header = int.from_bytes(message, "big")
        if header == 0:
            return
        elif type != 1:
            msg = self.sock_middleware.recv(header)
            return msg, None
        

    def _send_dict(self, d):
        encoded_msg = json.dumps(d).encode("utf-8")
        super().push(encoded_msg)

        
    def list_topics(self, callback: Callable):
        """Lists all topics available in the broker."""
        dic = {"command" : "list"}
        self._send_dict(dic)


    def cancel(self):
        """Cancel subscription."""
        dic = {"command": "nmsub", "topic": self.topic}
        self._send_dict(dic)


class JSONQueue(Queue):
    """Queue implementation with JSON based serialization."""

    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        super().__init__(topic, _type)

        dic = {"command": "ser", "serializer": "json"}
        msg = pickle.dumps(dic)
        super().push(msg)

        if _type == MiddlewareType.CONSUMER:
            dic = {"command": "sub", "topic": topic }
            encoded_msg = json.dumps(dic).encode("utf-8")
            super().push(encoded_msg)


    def push(self, value):
        print(f"value: {value} | topic: {self.topic}")
        dic = {"command": "pub", "topic": self.topic, "message": value}
        encoded_msg = json.dumps(dic).encode("utf-8")
        super().push(encoded_msg)


    def pull(self) -> (str, Any):
        msg, temp = super().pull()
        dic_msg = json.loads(msg)
        return dic_msg["topic"], dic_msg["message"]
        

class XMLQueue(Queue):
    """Queue implementation with XML based serialization."""

    def __init__(self,topic, _type=MiddlewareType.CONSUMER):
        super().__init__(topic, _type)

        dic = {"command": "ser", "serializer": "xml"}
        msg = pickle.dumps(dic)
        super().push(msg)       
        if _type == MiddlewareType.CONSUMER:
            root = XMLTree.Element('root')
            XMLTree.SubElement(root, 'command').set("value", "sub")
            XMLTree.SubElement(root, 'topic').set("value", str(topic))
            encoded_msg = XMLTree.tostring(root)
            super().push(encoded_msg) 

    def push(self, value):
        root = XMLTree.Element('root')
        XMLTree.SubElement(root, 'command').set("value", "pub")
        XMLTree.SubElement(root, 'topic').set("value", self.topic)
        XMLTree.SubElement(root, 'message').set("value", str(value))
        super().push(XMLTree.tostring(root))

    def pull(self) -> (str, Any):
        msg, temp = super().pull()
        tree = XMLTree.fromstring(msg)
        dic_msg = {}
        for child in tree:
            dic_msg[child.tag] = child.attrib["value"]
        return dic_msg["topic"], dic_msg["message"]


class PickleQueue(Queue):
    """Queue implementation with Pickle based serialization."""

    def __init__(self, topic, _type=MiddlewareType.CONSUMER):
        super().__init__(topic, _type)

        dic = {"command": "ser", "serializer": "pickle"}
        msg = pickle.dumps(dic)
        super().push(msg)

        if _type == MiddlewareType.CONSUMER:
            dic = {"command": "sub", "topic": topic }
            encoded_msg = pickle.dumps(dic)
            super().push(encoded_msg )


    def push(self, value):
        dic = {"command": "pub", "topic": self.topic, "message": value}
        encoded_msg = pickle.dumps(dic)
        super().push(encoded_msg)


    def pull(self) -> (str, Any):
        msg, temp = super().pull()
        dic_msg = pickle.loads(msg)
        return dic_msg["topic"], dic_msg["message"]
