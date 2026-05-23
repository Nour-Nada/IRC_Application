import socket
import sys
import json
import threading
from urllib import response

from classes import *

# Datastructures holding the state of the server
users = {}  # username -> user socket
users_lock = threading.Lock()  # lock for synchronizing access to users dict

rooms = {}  # room name -> users in rooms
rooms_lock = threading.Lock()  # lock for synchronizing access to rooms dict

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('localhost', 8080))

server.listen()
print("Server is listening on port 8080...")

def handle_client(client_socket, addr):
    opeartion_code = None #used to determine if the client sent a valid request and did not stop sending the neccessary data

    while True:
        try:
            response = None
            # varibles for checkindg data validity
            is_valid_data_length = True
            is_valid = True
            
            data = client_socket.recv(1024)
            if not data:
                break
            request = json.loads(data.decode())

            # Handle the request based on the operation code

            #before handling the request, we need to check if the data is valid
            if 'operation_message' in request: #checks the validity of the operation message data members
                if request['operation_message']['operation_code'] == 0x00:
                    is_valid = False
                elif len(request['operation_message']['sender']) == 0:
                    is_valid = False
                elif len(request['operation_message']['target']) == 0:
                    is_valid = False
                elif len(request['operation_message']['sender']) > 20:
                    is_valid = False
                elif len(request['operation_message']['target']) > 20:
                    is_valid = False
                if len(request['operation_message']['data']) == 0:
                    is_valid_data_length = False
            if 'message' in request: #checks the validity of the message data members
                if request['message']['header']['operation_code'] == 0x00:
                    is_valid = False
                elif len(request['message']['header']['sender']) == 0:
                    is_valid = False
                elif len(request['message']['header']['target']) == 0:
                    is_valid = False
                elif len(request['message']['header']['sender']) > 20:
                    is_valid = False
                elif len(request['message']['header']['target']) > 20:
                    is_valid = False
                elif len(request['message']['header']['length']) !=1024:
                    is_valid = False
                elif len(request['message']['data']) == 0:
                    is_valid = False
            if 'error_message' in request: #checks the validity of the error message data members
                if request['error_message']['err_code'] == 0x00:
                    is_valid = False
                elif len(request['error_message']['sender']) == 0:
                    is_valid = False
                elif len(request['error_message']['target']) == 0:
                    is_valid = False
                elif len(request['error_message']['sender']) > 20:
                    is_valid = False
                elif len(request['error_message']['target']) > 20:
                    is_valid = False
                elif len(request['error_message']['data']) == 0:
                    is_valid_data_length = False
                elif len(request['error_message']['data']) > 1024:
                    is_valid_data_length = False
        
            if is_valid == False: #if the data is not valid, we send an error message with the incorrect protocol error code
                response = error_message()
                response.err_code = 0x37
                response.data = "An incorrect protocol was used"
                response.target = request['operation_message']['sender']
                response.sender = "server"
            elif request['operation_message']['sender'].lower() not in users and request['operation_message']['operation_code'] != 0x21: #if the client does not exist we send an invalid client error code
                response = error_message()
                response.err_code = 0x39
                response.data = "The client listed does not exist"
                response.target = request['operation_message']['sender']
                response.sender = "server"
            elif request['operation_message']['operation_code'] == 0x21:  # connection to server
                if operation_code is not None:
                    response = error_message()
                    response.err_code = 0x37
                    response.data = "An incorrect protocol was used"
                    response.target = request['operation_message']['sender']
                    response.sender = "server"
                elif request['operation_message']['sender'].lower() in users:
                    response = error_message()
                    response.err_code = 0x33
                    response.data = "This name is already taken"
                    response.target = request['operation_message']['sender']
                    response.sender = "server"
                elif len(users) >= 100:
                    response = error_message()
                    response.err_code = 0x3b
                    response.data = "There are too many users"
                    response.target = request['operation_message']['sender']
                    response.sender = "server"
                else:
                    with users_lock:
                        users[request['operation_message']['sender'].lower()] = client_socket
                    response = operation_message()
                    response.operation_code = 0x2e
                    response.target = request['operation_message']['sender']
                    response.sender = "server"
                
                operation_code = None
            elif request['operation_message']['operation_code'] == 0x22: #create a room
                if operation_code is not None:
                    response = error_message()
                    response.err_code = 0x37
                    response.data = "An incorrect protocol was used"
                    response.target = request['operation_message']['sender']
                    response.sender = "server"
                elif request['operation_message']['data'].lower() in rooms:
                    response = error_message()
                    response.err_code = 0x34
                    response.data = "This room already exists"
                    response.target = request['operation_message']['sender']
                    response.sender = "server"
                elif len(rooms) >= 100:
                    response = error_message()
                    response.err_code = 0x3c
                    response.data = "There are too many rooms"
                    response.target = request['operation_message']['sender']
                    response.sender = "server"
                else:
                    with rooms_lock:
                        rooms[request['operation_message']['data'].lower()] = []
                    response = operation_message()
                    response.operation_code = 0x2e
                    response.target = request['operation_message']['sender']
                    response.sender = "server"
            elif request['operation_message']['operation_code'] == 0x23: #join a room
                if operation_code is not None:
                    response = error_message()
                    response.err_code = 0x37
                    response.data = "An incorrect protocol was used"
                    response.target = request['operation_message']['sender']
                    response.sender = "server"
                elif request['operation_message']['data'].lower() not in rooms:
                    response = error_message()
                    response.err_code = 0x38
                    response.data = "The room listed does not exist"
                    response.target = request['operation_message']['sender']
                    response.sender = "server"
                else:
                    with rooms_lock:
                        rooms[request['operation_message']['data'].lower()].append(request['operation_message']['sender'].lower())
                    response = operation_message()
                    response.operation_code = 0x2e
                    response.target = request['operation_message']['sender']
                    response.sender = "server"

            client_socket.sendall(json.dumps(response).encode('utf-8'))
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
            break
    
    client_socket.close()


while True:
    client_socket, addr = server.accept()
    print(f"Connection from {addr} has been established.")
    thread = threading.Thread(target=handle_client, args=(client_socket, addr))
    thread.start()

    client_socket.close()