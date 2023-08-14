""" Chord DHT node implementation. """
import socket
import threading
import logging
import pickle
from utils import dht_hash, contains


class FingerTable:
    """Finger Table."""

    def __init__(self, node_id, node_addr, m_bits=10):
        """ Initialize Finger Table."""
        self.fingertable = self.init_entries(m_bits,node_id,node_addr)
        self.node_id = node_id
        self.node_addr = node_addr
        self.m_bits = m_bits
        

    def fill(self, node_id, node_addr):
        """ Fill all entries of finger_table with node_id, node_addr."""
        for key in self.fingertable.keys():
            self.fingertable[key] = (node_id,node_addr)            
         
           

    def update(self, index, node_id, node_addr):
        """Update index of table with node_id and node_addr."""
        self.fingertable[index-1] = (node_id,node_addr)

    def find(self, identification): #id of the node we want to find
        """ Get node address of closest preceding node (in finger table) of identification. """
        for key in self.fingertable.keys():
            if contains(self.node_id, self.fingertable[key][0], identification): # caso contanha, retornar o endereço do nó anterior
                if key == 0:
                    return self.fingertable[self.m_bits - 1][1]
                else:
                    return self.fingertable[key-1][1]
        return self.fingertable[0][1]

    def refresh(self):
        """ Retrieve finger table entries requiring refresh."""
        fg_table = []
        #first bit
        bit = 0
        #for loop that iterates over the first new table creating entries
        while bit != self.m_bits:
            indice = self.node_id + 2**bit
            indice= indice% 2**self.m_bits
            fg_table.append((bit+1,indice,self.fingertable[bit][1]))
            self.fingertable[bit] = (indice,self.fingertable[bit][1])
            #new_entry
            bit = bit + 1   #next_bit, starting in 0 -> bits-1

        return fg_table
        
        

    def getIdxFromId(self, id):
        for key in self.fingertable.keys():
            indice = self.node_id + 2**key
            indice= indice% 2**self.m_bits
            if id == indice:
                return key + 1
        
        
            
        
        

    def __repr__(self):
        string = ""
        for f in self.fingertable.items():
            string += f'{str(f)}, '
        return string
    
    def init_entries(self,number_of_bits,id,addr):
        #new function to initialize all the entries of the finger_table in order to the bits
        fg_table = {}
        #first bit
        bit = 0
        #for loop that iterates over the first new table creating entries
        while bit != number_of_bits:
            indice = id + 2**bit
            indice= indice% 2**number_of_bits
            fg_table[bit] = (indice,addr);
            #new_entry
            bit = bit + 1   #next_bit, starting in 0 -> bits-1
        
        
        return fg_table
    
    
    
    @property
    def as_list(self):
        """return the finger table as a list of tuples: (identifier, (host, port)).
        NOTE: list index 0 corresponds to finger_table index 1
        """
        list_return = []
        for key in self.fingertable.keys():
            values_from_index = self.fingertable[key]
            list_return.append(values_from_index)

        return list_return

class DHTNode(threading.Thread):
    """ DHT Node Agent. """

    def __init__(self, address, dht_address=None, timeout=3):
        """Constructor
        Parameters:
            address: self's address
            dht_address: address of a node in the DHT
            timeout: impacts how often stabilize algorithm is carried out
        """
        threading.Thread.__init__(self)
        self.done = False
        self.identification = dht_hash(address.__str__())
        self.addr = address  # My address
        self.dht_address = dht_address  # Address of the initial Node
        if dht_address is None:
            self.inside_dht = True
            # I'm my own successor
            self.successor_id = self.identification
            self.successor_addr = address
            self.predecessor_id = None
            self.predecessor_addr = None
        else:
            self.inside_dht = False
            self.successor_id = None
            self.successor_addr = None
            self.predecessor_id = None
            self.predecessor_addr = None

        #TODO create finger_table
        self.finger_table = FingerTable(self.identification, self.addr)

        self.keystore = {}  # Where all data is stored
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(timeout)
        self.logger = logging.getLogger("Node {}".format(self.identification))

    def send(self, address, msg):
        """ Send msg to address. """
        payload = pickle.dumps(msg)
        self.socket.sendto(payload, address)

    def recv(self):
        """ Retrieve msg payload and from address."""
        try:
            payload, addr = self.socket.recvfrom(1024)
        except socket.timeout:
            return None, None

        if len(payload) == 0:
            return None, addr
        return payload, addr

    def node_join(self, args):
        """Process JOIN_REQ message.
        Parameters:
            args (dict): addr and id of the node trying to join
        """ 

        self.logger.debug("Node join: %s", args)
        addr = args["addr"]
        identification = args["id"]
        if self.identification == self.successor_id:  # I'm the only node in the DHT
            self.successor_id = identification
            self.successor_addr = addr
            #TODO update finger table

            lista = self.finger_table.as_list
            for key in self.finger_table.fingertable.keys():
                id_lista = lista[key][0]
                in_bet = contains(self.identification, self.successor_id, self.finger_table.fingertable[key][0])
                if id_lista == self.identification or in_bet:
                    self.finger_table.update(key+1, self.successor_id, self.successor_addr)
                

            args = {"successor_id": self.identification, "successor_addr": self.addr}
            self.send(addr, {"method": "JOIN_REP", "args": args})
        elif contains(self.identification, self.successor_id, identification):
            args = {
                "successor_id": self.successor_id,
                "successor_addr": self.successor_addr,
            }
            self.successor_id = identification
            self.successor_addr = addr
            #TODO update finger table
            lista = self.finger_table.as_list
            for key in self.finger_table.fingertable.keys():
                id_lista = lista[key][0]
                in_bet = contains(self.identification, self.successor_id, self.finger_table.fingertable[key][0])
                if id_lista == self.identification or in_bet:
                    self.finger_table.update(key+1, self.successor_id, self.successor_addr)
                

            self.send(addr, {"method": "JOIN_REP", "args": args})
        else:
            self.logger.debug("Find Successor(%d)", args["id"])
            self.send(self.successor_addr, {"method": "JOIN_REQ", "args": args})
        self.logger.info(self)


    def get_successor(self, args):
        """Process SUCCESSOR message.
        Parameters:
            args (dict): addr and id of the node asking
        """

        self.logger.debug("Get successor: %s", args)
        #TODO Implement processing of SUCCESSOR message
        
        

        if (contains(self.identification, self.successor_id, args["id"])):
            self.send(args["from"], {"method": "SUCCESSOR_REP", "args": {"req_id": args["id"], "successor_id" : self.successor_id, "successor_addr": self.successor_addr}})
        else:
            self.send(self.finger_table.find(args["id"]), {"method": "SUCCESSOR", "args": {"id": args["id"], "from" : args["from"]}})

                
    def notify(self, args):
        """Process NOTIFY message.
            Updates predecessor pointers.
        Parameters:
            args (dict): id and addr of the predecessor node
        """

        self.logger.debug("Notify: %s", args)
        if self.predecessor_id is None or contains(
            self.predecessor_id, self.identification, args["predecessor_id"]
        ):
            self.predecessor_id = args["predecessor_id"]
            self.predecessor_addr = args["predecessor_addr"]
        self.logger.info(self)

    def stabilize(self, from_id, addr):
        """Process STABILIZE protocol.
            Updates all successor pointers.
        Parameters:
            from_id: id of the predecessor of node with address addr
            addr: address of the node sending stabilize message
        """

        self.logger.debug("Stabilize: %s %s", from_id, addr)
        if from_id is not None and contains(
            self.identification, self.successor_id, from_id
        ):
            # Update our successor
            self.successor_id = from_id
            self.successor_addr = addr
            #TODO update finger table
            lista = self.finger_table.as_list
            for key in self.finger_table.fingertable.keys():
                id_lista = lista[key][0]
                in_bet = contains(self.identification, self.successor_id, self.finger_table.fingertable[key][0])
                if id_lista == self.identification or in_bet:
                    self.finger_table.update(key+1, self.successor_id, self.successor_addr)
                

        # notify successor of our existence, so it can update its predecessor record
        args = {"predecessor_id": self.identification, "predecessor_addr": self.addr}
        self.send(self.successor_addr, {"method": "NOTIFY", "args": args})

        # TODO refresh finger_table
        new_lst = []
        lst = self.finger_table.refresh()
        for each in lst:
            new_lst.append(each[1])
            for each2 in new_lst:

                self.get_successor({"id": each2 , "from" : self.addr})
        

    def put(self, key, value, address):
        """Store value in DHT.
        Parameters:
        key: key of the data
        value: data to be stored
        address: address where to send ack/nack
        """


        key_hash = dht_hash(key) #hashed key
        self.logger.debug("Put: %s %s", key, key_hash)
        client_addr = address

        #vars
        ack = {"method": "ACK"}
        nxt_msg = {"method": "PUT", "args": {"key": key, "value": value,"from": client_addr}}
        
        #bol to know if its to be inserted here or in another location
        is_here = contains(self.predecessor_id,self.identification,key_hash)
        is_next = contains(self.identification,self.successor_id,key_hash)

        #conditions
        if is_here:
            if key in self.keystore:
                #if key is already in the list that stores the keys then its not acknowledge
                return "IF ENTERS HERE IS WRONG"
            else:
                #if is not we store the key and send the acknowledge message
                self.keystore[key] = value
                self.send(address,ack)
        elif is_next:
                self.send(self.successor_addr,nxt_msg)   
        else: #insert on the fingertable,until there sendo to the next node
                self.send(self.finger_table.find(key_hash),nxt_msg)



    def get(self, key, address):
        """Retrieve value from DHT.
        Parameters:
        key: key of the data
        address: address where to send ack/nack
        """
        key_hash = dht_hash(key)
        self.logger.debug("Get: %s %s", key, key_hash)
        
        
        #bol to know if its to be inserted here or in another location
        is_here = contains(self.predecessor_id,self.identification,key_hash)
        client_addr = address
        is_next = contains(self.identification, self.successor_id, key_hash)
        nxt_msg = {"method": "GET", "args": {"key": key, "from":client_addr}}

        #conditions
        if is_here:
            if key in self.keystore:
                value = self.keystore[key]
                self.send(address,{'method': 'ACK', "args": value})
        elif is_next:
            self.send(self.successor_addr, nxt_msg)
        else:
            self.send(self.finger_table.find(key_hash),nxt_msg)


    def run(self):
        self.socket.bind(self.addr)
        
        # Loop untiln joining the DHT
        while not self.inside_dht:
            join_msg = {
                "method": "JOIN_REQ",
                "args": {"addr": self.addr, "id": self.identification},
            }
            self.send(self.dht_address, join_msg)
            payload, addr = self.recv()
            
            if payload is not None:
                
                output = pickle.loads(payload)
                self.logger.debug("O: %s", output)
                if output["method"] == "JOIN_REP":
                    args = output["args"]
                    self.successor_id = args["successor_id"]
                    self.successor_addr = args["successor_addr"]
                    #TODO fill finger table
                    self.finger_table.fill(self.successor_id, self.successor_addr)

                    self.inside_dht = True
                    self.logger.info(self)

        while not self.done:
            payload, addr = self.recv()
            if payload is not None:
                output = pickle.loads(payload)
                self.logger.info("O: %s", output)
                if output["method"] == "JOIN_REQ":
                    self.node_join(output["args"])
                elif output["method"] == "NOTIFY":
                    self.notify(output["args"])
                elif output["method"] == "PUT":
                    self.put(
                        output["args"]["key"],
                        output["args"]["value"],
                        output["args"].get("from", addr),
                    )
                elif output["method"] == "GET":
                    self.get(output["args"]["key"], output["args"].get("from", addr))
                elif output["method"] == "PREDECESSOR":
                    # Reply with predecessor id
                    self.send(
                        addr, {"method": "STABILIZE", "args": self.predecessor_id}
                    )
                elif output["method"] == "SUCCESSOR":
                    self.get_successor(output["args"])
                elif output["method"] == "STABILIZE":
                    # Initiate stabilize protocol
                    self.stabilize(output["args"], addr)
                elif output["method"] == "SUCCESSOR_REP":
                    #TODO Implement processing of SUCCESSOR_REP
                    id = output["args"]["req_id"]
                    idx = self.finger_table.getIdxFromId(id)
                    if (idx != None):
                        self.finger_table.update(idx, output["args"]["successor_id"], output["args"]["successor_addr"])

            else:  
                self.send(self.successor_addr, {"method": "PREDECESSOR"})

    def __str__(self):
        return "Node ID: {}; DHT: {}; Successor: {}; Predecessor: {}; FingerTable: {}".format(
            self.identification,
            self.inside_dht,
            self.successor_id,
            self.predecessor_id,
            self.finger_table,
        )

    def __repr__(self):
        return self.__str__()
