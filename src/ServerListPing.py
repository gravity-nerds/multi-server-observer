import socket
import struct
import json

def read_var_int(sock):
    i = 0
    j = 0
    while True:
        k = sock.recv(1)
        if not k:
            return 0
        k = k[0]
        i |= (k & 0x7f) << (j * 7)
        j += 1
        if j > 5:
            raise ValueError("var_int too big")
        if not (k & 0x80):
            return i

def ping(ip, port):
    sock = socket.socket()

    data = None

    try:
        sock.connect((ip, port))
        
        host = ip.encode("utf-8")

        data = b""
        data += b"\x00"
        data += b"\x04"
        data += struct.pack(">b", len(host)) + host
        data += struct.pack(">H", port)
        data += b"\x01"
        data = struct.pack(">b", len(data)) + data
        sock.sendall(data + b"\x01\x00")
        
        length = read_var_int(sock)

        if length < 10:
            if length < 0:
                raise ValueError("Negative Length Read")
            else:
                raise ValueError("Invalid Response %s" % sock.read(length))
            
        sock.recv(1)
        length = read_var_int(sock)
        data = b""

        while len(data) != length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                raise ValueError("connection aborted")
            
            data += chunk
    finally:
        sock.close()
    
    if data != None:
        return True, json.loads(data)
    return False, None

if __name__ == "__main__":
    print(ping("192.168.1.72", 25565))