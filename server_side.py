import socket
import json
import threading
from classes import *

# Datastructures holding the state of the server
users = {}  # username -> user socket
users_lock = threading.Lock()  # lock for synchronizing access to users dict

rooms = {}  # room name -> users in rooms
rooms_lock = threading.Lock()  # lock for synchronizing access to rooms dict

#Global variables
SERVER_NAME = "server"
TIMEOUT_TIME = 30.0

def handle_errors(err_code, data, target, sender): #creates an operation_variable object and sends it back
    response = error_message()
    response.err_code = err_code
    response.data = data
    response.target = target
    response.sender = sender
    return response

def handle_operation(err_code, target, sender): #creates an operation_variable object and sends it back
    response = operation_message()
    response.err_code = err_code
    response.target = target
    response.sender = sender
    return response

def disconnect(user_name): #removes the users from the lists that way when they disconnect they don't persist in the variables
    with users_lock:
        del users[user_name]
    for room in rooms:
        if user_name in rooms[room]:
            with rooms_lock:
                rooms[room].remove(user_name)

def handle_client(client_socket, addr):
    operation_code = None #used to determine if the client sent a valid request and did not stop sending the neccessary data
    user_name = None

    while True:
        try:
            response = None
            send_response = True #checks if response was already sent
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
        
            #Routing checks that respond back to the client
            if is_valid == False: #if the data is not valid, we send an error message with the incorrect protocol error code
                response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)

            elif is_valid_data_length == False:
                response = handle_errors(0x3a, "The length of the data is too long", request['operation_message']['sender'], SERVER_NAME)
            
            elif request['operation_message']['sender'].lower() not in users and request['operation_message']['operation_code'] != 0x21: #if the client does not exist we send an invalid client error code
                response = handle_errors(0x39, "The client listed does not exist", request['operation_message']['sender'], SERVER_NAME)
            
            elif request['operation_message']['operation_code'] == 0x21:  # connection to server
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)
                    operation_code = None
                elif request['operation_message']['sender'].lower() in users:
                    response = handle_errors(0x33, "This name is already taken", request['operation_message']['sender'], SERVER_NAME)
                elif request['operation_message']['sender'].lower() == "server":
                    response = handle_errors(0x34, "This name is invalid", request['operation_message']['sender'], SERVER_NAME)
                elif len(users) >= 100:
                    response = handle_errors(0x3b, "There are too many users", request['operation_message']['sender'], SERVER_NAME)
                else:
                    with users_lock:
                        users[request['operation_message']['sender'].lower()] = client_socket
                    user_name = request['operation_message']['sender'].lower()
                    print(f"A new connection with {user_name} was established")
                    response = handle_operation(0x2e, request['operation_message']['sender'], SERVER_NAME)
            
            elif request['operation_message']['operation_code'] == 0x22: #create a room
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)
                    operation_code = None
                elif request['operation_message']['data'].lower() in rooms:
                    response = handle_errors(0x34, "This room already exists", request['operation_message']['sender'], SERVER_NAME)
                elif len(rooms) >= 100:
                    response = handle_errors(0x3c, "There are too many rooms", request['operation_message']['sender'], SERVER_NAME)
                else:
                    with rooms_lock:
                        rooms[request['operation_message']['data'].lower()] = []
                    response = handle_operation(0x2e, request['operation_message']['sender'], SERVER_NAME)
            
            elif request['operation_message']['operation_code'] == 0x23: #join a room
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)
                    operation_code = None
                elif request['operation_message']['data'].lower() not in rooms:
                    response = handle_errors(0x38, "The room listed does not exist", request['operation_message']['sender'], SERVER_NAME)
                else:
                    with rooms_lock:
                        rooms[request['operation_message']['data'].lower()].append(request['operation_message']['sender'].lower())
                    response = handle_operation(0x2e, request['operation_message']['sender'], SERVER_NAME)
                
            elif request['operation_message']['operation_code'] == 0x24: #leave a room
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)
                    operation_code = None
                elif request['operation_message']['data'].lower() not in rooms:
                    response = handle_errors(0x38, "The room listed does not exist", request['operation_message']['sender'], SERVER_NAME)
                elif request['operation_message']['sender'].lower() not in rooms[request['operation_message']['data'].lower()]:
                    response = handle_errors(0x36, "An invlid operation was attempted", request['operation_message']['sender'], SERVER_NAME)
                else:
                    with rooms_lock:
                        rooms[request['operation_message']['data'].lower()].remove(request['operation_message']['sender'].lower())
                    response = handle_operation(0x2e, request['operation_message']['sender'], SERVER_NAME)
            
            elif request['operation_message']['operation_code'] == 0x25: #disconnect
                send_response = False
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)
                    operation_code = None
                else:
                    disconnect(request['operation_message']['sender'].lower())
                    response = handle_operation(0x2e, request['operation_message']['sender'], SERVER_NAME)
                    client_socket.sendall(json.dumps(response).encode('utf-8'))
                    break
            
            elif request['operation_message']['operation_code'] == 0x26: #list members in a room
                send_response = False
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)
                    operation_code = None
                    send_response = True
                elif request['operation_message']['data'].lower() not in rooms:
                    response = handle_errors(0x38, "The room listed does not exist", request['operation_message']['sender'], SERVER_NAME)
                else:
                    for user in rooms[request['operation_message']['data'].lower()]:
                        response = message()
                        response.header.operation_code = 0x13
                        response.header.target = request['operation_message']['sender']
                        response.header.sender = SERVER_NAME
                        response.data = user
                        json_response = json.dumps(response.to_dict()).encode('utf-8')
                        client_socket.sendall(json_response)
                if send_response == False:
                    response = handle_operation(0x27, request['operation_message']['sender'], SERVER_NAME)
                    client_socket.sendall(json.dumps(response).encode('utf-8'))

            elif request['operation_message']['operation_code'] == 0x28: #list rooms
                send_response = False
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)
                    operation_code = None
                    send_response = True
                elif request['operation_message']['data'].lower() not in rooms:
                    response = handle_errors(0x38, "The room listed does not exist", request['operation_message']['sender'], SERVER_NAME)
                else:
                    for room in rooms:
                        response = message()
                        response.header.operation_code = 0x14
                        response.header.target = request['operation_message']['sender']
                        response.header.sender = SERVER_NAME
                        response.data = room
                        json_response = json.dumps(response.to_dict()).encode('utf-8')
                        client_socket.sendall(json_response)
                if send_response == False:
                    response = handle_operation(0x29, request['operation_message']['sender'], SERVER_NAME)
                    client_socket.sendall(json.dumps(response).encode('utf-8'))
                
            elif request['operation_message']['operation_code'] == 0x2a or operation_code == 0x2a: #send a message to a user or a room
                send_response = False
                operation_code = 0x2a
                if request['operation_message']['target'].lower() not in rooms:
                    response = handle_errors(0x38, "The room listed does not exist", request['operation_message']['sender'], SERVER_NAME)
                    send_response = True
                    operation_code = None
                elif request['operation_message']['operation_code'] != 0x2a and request['operation_message']['operation_code'] != 0x2b:
                    response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)
                    operation_code = None
                elif request['operation_message']['operation_code'] == 0x2a:
                    response = request.encode('utf-8')
                    client_socket.settimeout(TIMEOUT_TIME) #sets a timeout timer for all coming in message pieces until the closing message comes
                elif request['operation_message']['operation_code'] == 0x2b:
                    response = request.encode('utf-8')
                    operation_code = None
                    client_socket.settimeout(None)
                else:
                    response = request.encode('utf-8')
                if send_response == False:
                    sent_response = False
                    if request['operation_message']['target'] in users: #sends to a user
                        try:
                            target_socket = users[request['operation_message']['target'].lower()]
                            target_socket.sendall(json.dumps(response).encode('utf-8'))
                        except Exception as e:
                            disconnect(request['operation_message']['target'].lower())
                    elif request['operation_message']['target'] in rooms: #sends to a room
                        for user in rooms[request['operation_message']['target']]:
                            try:
                                target_socket = users[user]
                                target_socket.sendall(json.dumps(response).encode('utf-8'))
                            except Exception as e:
                                print(f"The client of the name {user} no longer exists")
                                disconnect(user)
                    else:
                        response = handle_errors(0x39, "The client listed does not exist", request['operation_message']['sender'], SERVER_NAME)
                        client_socket.sendall(json.dumps(response).encode('utf-8'))
                        sent_response = True
                    if sent_response != True: #sends a succses message back to the client if a message was not already sent to them
                        response = handle_operation(0x2e, request['operation_message']['sender'], SERVER_NAME)
                        client_socket.sendall(json.dumps(response).encode('utf-8'))

            elif request['operation_message']['operation_code'] == 0x2c or operation_code == 0x2c: #send a file to a user or a room
                send_response = False
                operation_code = 0x2c
                if request['operation_message']['target'].lower() not in rooms:
                    response = handle_errors(0x38, "The room listed does not exist", request['operation_message']['sender'], SERVER_NAME)
                    send_response = True
                    operation_code = None
                elif request['operation_message']['operation_code'] != 0x2c and request['operation_message']['operation_code'] != 0x2d:
                    response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)
                    operation_code = None
                elif request['operation_message']['operation_code'] == 0x2c:
                    response = request.encode('utf-8')
                    client_socket.settimeout(TIMEOUT_TIME) #sets a timeout timer for all coming in message pieces until the closing message comes
                elif request['operation_message']['operation_code'] == 0x2d:
                    response = request.encode('utf-8')
                    operation_code = None
                    client_socket.settimeout(None)
                else:
                    response = request.encode('utf-8')
                if send_response == False:
                    sent_response = False
                    if request['operation_message']['target'] in users: #sends to a user
                        try:
                            target_socket = users[request['operation_message']['target'].lower()]
                            target_socket.sendall(json.dumps(response).encode('utf-8'))
                        except Exception as e:
                            print(f"The client of the name {request['operation_message']['target'].lower()} no longer exists")
                            disconnect(request['operation_message']['target'].lower())
                    elif request['operation_message']['target'] in rooms: #sends to a room
                        for user in rooms[request['operation_message']['target']]:
                            try:
                                target_socket = users[user]
                                target_socket.sendall(json.dumps(response).encode('utf-8'))
                            except Exception as e:
                                print(f"The client of the name {user} no longer exists")
                                disconnect(user)
                    else:
                        response = handle_errors(0x39, "The client listed does not exist", request['operation_message']['sender'], SERVER_NAME)
                        client_socket.sendall(json.dumps(response).encode('utf-8'))
                        sent_response = True
                    if sent_response != True: #sends a succses message back to the client if a message was not already sent to them
                        response = handle_operation(0x2e, request['operation_message']['sender'], SERVER_NAME)
                        client_socket.sendall(json.dumps(response).encode('utf-8'))

            elif request['error_message'] or request['message']:
                response = handle_errors(0x37, "An incorrect protocol was used", request['operation_message']['sender'], SERVER_NAME)
            else:
                response = handle_errors(0x3d, "An unknown error occured", request['operation_message']['sender'], SERVER_NAME)
                

            if send_response == True:
                client_socket.sendall(json.dumps(response).encode('utf-8'))
        except socket.timeout:
            print("The opearation was not completed due to a timeout")
            response = handle_errors(0x35, "Client timed out due to inactivity", request['operation_message']['sender'], SERVER_NAME)
            client_socket.sendall(json.dumps(response).encode('utf-8'))
        except (BrokenPipeError, ConnectionResetError, OSError) as e: #attempts to catch specfic errors first to avoid catching general erros before moving to the general error catch
            print(f"The client of the name {user_name} no longer exists")
            disconnect(user_name)
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
            print(f"The client of the name {user_name} no longer exists")
            disconnect(user_name)
            break
        finally:
            client_socket.settimeout(None)
    
    client_socket.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('localhost', 8080))

    server.listen()
    print("Server is listening on port 8080...")

    server.settimeout(1.0)

    while True:
        try:
            client_socket, addr = server.accept()
            print(f"Connection from {addr} has been established.")
            thread = threading.Thread(target=handle_client, args=(client_socket, addr))
            thread.daemon = True
            thread.start()
        except socket.timeout:
            continue
        except KeyboardInterrupt:
            print("Shutting down server...")
            break

if __name__ == "__main__":
    main()