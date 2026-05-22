import socket
import sys
import json

from classes import *

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('localhost', 8080))

server.listen(5)
print("Server is listening on port 8080...")

while True:
    client_socket, addr = server.accept()
    print(f"Connection from {addr} has been established.")

    request = client_socket.recv(sys.getsizeof(message)*4 + 1024*4).decode('utf-8')
    print(f"Received request: {request}")

    response = "HTTP/1.1 200 OK\n\nHello, World!"
    client_socket.sendall(response.encode('utf-8'))

    client_socket.close()