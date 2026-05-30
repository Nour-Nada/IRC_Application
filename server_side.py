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

def handle_operation(code, target, sender): #creates an operation_variable object and sends it back
    response = operation_message()
    response.operation_code = code
    response.target = target
    response.sender = sender
    return response

def disconnect(user_name): #removes the users from the lists that way when they disconnect they don't persist in the variables
    global users
    global users_lock
    global rooms
    global rooms_lock
    if user_name in users:
        with users_lock:
            del users[user_name]
        for room in rooms:
            if user_name in rooms[room]:
                with rooms_lock:
                    rooms[room].remove(user_name)

def handle_client(client_socket, addr):
    global users
    global users_lock
    global rooms
    global rooms_lock

    operation_code = None #used to determine if the client sent a valid request and did not stop sending the neccessary data
    user_name = None
    safe_disconnect = False

    while True:
        try:
            response = None
            send_response = True #checks if response was already sent
            # varibles for checkindg data validity
            is_valid_data_length = True #checks to maek sure the data is a valid length
            no_data = True #checks to see if there is any data with the messsage for operation and error messages
            is_valid = True #checks for the general validity of the incoming message
            sender = None
            target = None
            
            data = client_socket.recv(4096)
            if not data:
                break
            request = json.loads(data.decode())

            #for testing purposes
            print(f"{request}") #for testing purposes
            for user in users:
                print(f"{user}")

            if 'operation_message' in request: sender = request['operation_message']['sender']
            elif 'error_message' in request: sender = request['error_message']['sender']
            else: sender = request['message']['header']['sender']

            if 'operation_message' in request: target = request['operation_message']['target']
            elif 'error_message' in request: target = request['error_message']['target']
            else: target = request['message']['header']['target']

            # Handle the request based on the operation code

            #before handling the request, we need to check if the data is valid
            if 'operation_message' in request: #checks the validity of the operation message data members
                if request['operation_message']['operation_code'] == 0x00:
                    is_valid = False
                elif len(sender) == 0:
                    is_valid = False
                elif len(target) == 0:
                    is_valid = False
                elif len(sender) > 20:
                    is_valid = False
                elif len(target) > 20:
                    is_valid = False
                elif sender == SERVER_NAME:
                    is_valid = False
                elif len(request['operation_message']['data']) == 0:
                    no_data = False
            if 'message' in request: #checks the validity of the message data members
                if request['message']['header']['operation_code'] == 0x00:
                    is_valid = False
                elif len(sender) == 0:
                    is_valid = False
                elif len(target) == 0:
                    is_valid = False
                elif len(sender) > 20:
                    is_valid = False
                elif len(target) > 20:
                    is_valid = False
                elif request['message']['header']['length'] > 1024:
                    is_valid = False
                elif len(request['message']['data']) == 0:
                    is_valid = False
                elif len(request['message']['data']) > 1024:
                    is_valid = False
                elif sender == SERVER_NAME:
                    is_valid = False
            if 'error_message' in request: #checks the validity of the error message data members
                if request['error_message']['err_code'] == 0x00:
                    is_valid = False
                elif len(sender) == 0:
                    is_valid = False
                elif len(target) == 0:
                    is_valid = False
                elif len(sender) > 20:
                    is_valid = False
                elif len(target) > 20:
                    is_valid = False
                elif len(request['error_message']['data']) > 1024:
                    is_valid_data_length = False
                elif sender == SERVER_NAME:
                    is_valid = False
                elif len(request['error_message']['data']) == 0:
                    no_data = False
        
            #Routing checks that respond back to the client
            if is_valid == False: #if the data is not valid, we send an error message with the incorrect protocol error code
                response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)

            elif is_valid_data_length == False:
                sender = None
                response = handle_errors(0x3a, "The length of the data is wrong", sender, SERVER_NAME)
            
            elif 'operation_message' in request and sender.lower() not in users and request['operation_message']['operation_code'] != 0x21: #if the client does not exist we send an invalid client error code
                sender = None
                response = handle_errors(0x39, "The client listed does not exist", sender, SERVER_NAME)
            
            elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x21:  # connection to server
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)
                    operation_code = None
                elif no_data == False:
                    response = handle_errors(0x3a, "The length of the data is wrong", sender, SERVER_NAME)
                elif sender.lower() in users or sender.lower() in rooms:
                    response = handle_errors(0x33, "This name is already taken", sender, SERVER_NAME)
                elif sender.lower() == "server":
                    response = handle_errors(0x34, "This name is invalid", sender, SERVER_NAME)
                elif len(users) >= 100:
                    response = handle_errors(0x3b, "There are too many users", sender, SERVER_NAME)
                else:
                    with users_lock:
                        users[sender.lower()] = client_socket
                    user_name = sender.lower()
                    print(f"A new connection with {user_name} was established")
                    response = handle_operation(0x2e, sender, SERVER_NAME)
            
            elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x22: #create a room
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)
                    operation_code = None
                elif no_data == False:
                    response = handle_errors(0x3a, "The length of the data is wrong", sender, SERVER_NAME)
                elif request['operation_message']['data'].lower() in rooms or request['operation_message']['data'].lower() in users:
                    response = handle_errors(0x34, "This name is already taken", sender, SERVER_NAME)
                elif len(rooms) >= 100:
                    response = handle_errors(0x3c, "There are too many rooms", sender, SERVER_NAME)
                else:
                    with rooms_lock:
                        rooms[request['operation_message']['data'].lower()] = []
                    response = handle_operation(0x2e, sender, SERVER_NAME)
            
            elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x23: #join a room
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)
                    operation_code = None
                elif no_data == False:
                    response = handle_errors(0x3a, "The length of the data is wrong", sender, SERVER_NAME)
                elif request['operation_message']['data'].lower() not in rooms:
                    response = handle_errors(0x38, "The room listed does not exist", sender, SERVER_NAME)
                else:
                    with rooms_lock:
                        rooms[request['operation_message']['data'].lower()].append(sender.lower())
                    response = handle_operation(0x2e, sender, SERVER_NAME)
                
            elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x24: #leave a room
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)
                    operation_code = None
                elif no_data == False:
                    response = handle_errors(0x3a, "The length of the data is wrong", sender, SERVER_NAME)
                elif request['operation_message']['data'].lower() not in rooms:
                    response = handle_errors(0x38, "The room listed does not exist", sender, SERVER_NAME)
                elif sender.lower() not in rooms[request['operation_message']['data'].lower()]:
                    response = handle_errors(0x36, "An invlid operation was attempted", sender, SERVER_NAME)
                else:
                    with rooms_lock:
                        rooms[request['operation_message']['data'].lower()].remove(sender.lower())
                    response = handle_operation(0x2e, sender, SERVER_NAME)
            
            elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x25: #disconnect
                send_response = False
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)
                    operation_code = None
                else:
                    safe_disconnect = True
                    disconnect(sender.lower())
                    response = handle_operation(0x2e, sender, SERVER_NAME)
                    client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))
                    break
            
            elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x26: #list members in a room
                send_response = False
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)
                    operation_code = None
                    send_response = True
                elif no_data == False:
                    send_response = True
                    response = handle_errors(0x3a, "The length of the data is wrong", sender, SERVER_NAME)
                elif request['operation_message']['data'].lower() not in rooms:
                    send_response = True
                    response = handle_errors(0x38, "The room listed does not exist", sender, SERVER_NAME)
                else:
                    for user in rooms[request['operation_message']['data'].lower()]: #sends the data to every user in the room
                        response = message()
                        response.header.operation_code = 0x13
                        response.header.target = sender
                        response.header.sender = SERVER_NAME
                        response.data = user
                        client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))
                if send_response == False:
                    response = handle_operation(0x27, sender, SERVER_NAME)
                    client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))

            elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x28: #list rooms
                send_response = False
                if operation_code is not None:
                    response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)
                    operation_code = None
                    send_response = True
                else:
                    for room in rooms: #sends the data to every user in the room
                        response = message()
                        response.header.operation_code = 0x14
                        response.header.target = sender
                        response.header.sender = SERVER_NAME
                        response.data = room
                        client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))
                if send_response == False:
                    response = handle_operation(0x29, sender, SERVER_NAME)
                    client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))
                
            elif ('operation_message' in request and request['operation_message']['operation_code'] == 0x2a) or operation_code == 0x2a: #send a message to a user or a room
                send_response = False
                operation_code = 0x2a
                if target.lower() not in rooms and target.lower() not in users:
                    response = handle_errors(0x39, "The client listed does not exist", sender, SERVER_NAME)
                    send_response = True
                    operation_code = None
                elif 'operation_message' in request and request['operation_message']['operation_code'] != 0x2a and request['operation_message']['operation_code'] != 0x2b:
                    response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)
                    operation_code = None
                elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x2a:
                    response = json.dumps(request).encode('utf-8')
                    client_socket.settimeout(TIMEOUT_TIME) #sets a timeout timer for all coming in message pieces until the closing message comes
                elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x2b:
                    response = json.dumps(request).encode('utf-8')
                    operation_code = None
                    client_socket.settimeout(None)
                else:
                    response = request
                if send_response == False:
                    sent_response = False
                    if ('operation_message' in request and target in users) or ('message' in request and target in users): #sends to a user
                        try:
                            target_socket = users[target.lower()]
                            target_socket.sendall(json.dumps(response.to_dict() + '\n').encode('utf-8'))
                        except Exception as e:
                            disconnect(target.lower())
                    elif ('operation_message' in request and target in rooms) or ('message' in request and target in rooms): #sends to a room
                        for user in rooms[target]:
                            try:
                                target_socket = users[user]
                                target_socket.sendall(json.dumps(response.to_dict() + '\n').encode('utf-8'))
                            except Exception as e:
                                print(f"The client of the name {user} no longer exists")
                                disconnect(user)
                    else:
                        response = handle_errors(0x39, "The client listed does not exist", sender, SERVER_NAME)
                        client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))
                        sent_response = True
                    if sent_response != True: #sends a succses message back to the client if a message was not already sent to them
                        response = handle_operation(0x2e, sender, SERVER_NAME)
                        client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))

            elif ('operation_message' in request and request['operation_message']['operation_code'] == 0x2c) or operation_code == 0x2c: #send a file to a user or a room
                send_response = False
                operation_code = 0x2c
                if 'operation_message' in request and target.lower() not in rooms and target.lower() not in users:
                    response = handle_errors(0x39, "The client listed does not exist", sender, SERVER_NAME)
                    send_response = True
                    operation_code = None
                elif 'operation_message' in request and request['operation_message']['operation_code'] != 0x2c and request['operation_message']['operation_code'] != 0x2d:
                    response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)
                    operation_code = None
                elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x2c:
                    response = request
                    client_socket.settimeout(TIMEOUT_TIME) #sets a timeout timer for all coming in message pieces until the closing message comes
                elif 'operation_message' in request and request['operation_message']['operation_code'] == 0x2d:
                    response = request
                    operation_code = None
                    client_socket.settimeout(None)
                else:
                    response = request
                if send_response == False:
                    sent_response = False
                    if ('operation_message' in request and target in users) or ('message' in request and target in users): #sends to a user
                        try:
                            target_socket = users[target.lower()]
                            target_socket.sendall(json.dumps(response.to_dict() + "\n").encode('utf-8'))
                        except Exception as e:
                            print(f"The client of the name {target.lower()} no longer exists")
                            disconnect(target.lower())
                    elif ('operation_message' in request and target in rooms) or ('message' in request and target in rooms): #sends to a room
                        for user in rooms[target]:
                            try:
                                target_socket = users[user]
                                target_socket.sendall(json.dumps(response.to_dict()).encode('utf-8'))
                            except Exception as e:
                                print(f"The client of the name {user} no longer exists")
                                disconnect(user)
                    else:
                        response = handle_errors(0x39, "The client listed does not exist", sender, SERVER_NAME)
                        client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))
                        sent_response = True
                    if sent_response != True: #sends a succses message back to the client if a message was not already sent to them
                        response = handle_operation(0x2e, sender, SERVER_NAME)
                        client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))

            elif 'error_message' in request or 'message' in request:
                response = handle_errors(0x37, "An incorrect protocol was used", sender, SERVER_NAME)
            else:
                response = handle_errors(0x3d, "An unknown error occured", sender, SERVER_NAME)
                

            if send_response == True:
                client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))
        except socket.timeout: #catches timeouts
            print("The opearation was not completed due to a timeout")
            response = handle_errors(0x35, "Client timed out due to inactivity", sender, SERVER_NAME)
            client_socket.sendall((json.dumps(response.to_dict()) + "\n").encode('utf-8'))
        except ConnectionResetError as e: #catches when the client disconnects
            if safe_disconnect == False:
                print(f"The client of the name '{user_name}' probably forcibly disconnected (if they did not register a name yet they will by default be called 'None')")
            else:
                print(f"The client of the name {user_name} saftely disconnected (if they did not register a name yet they will by default be called 'None')")
            disconnect(user_name)
            break
        except (BrokenPipeError, ConnectionResetError, OSError) as e: #attempts to catch specfic errors first to avoid catching general errors before moving to the general error catch
            print(f"The client of the name {user_name} no longer exists")
            disconnect(user_name)
            break
        except KeyboardInterrupt: #makes Ctrl+C operations look nicer
            print("Shutting down server...")
            break
        # except Exception as e: #catches all other exceptions
        #     print(f"Error handling client {addr}: {e}")
        #     print(f"The client of the name {user_name} no longer exists")
        #     disconnect(user_name)
        #     break
        finally:
            client_socket.settimeout(None)
    
    client_socket.close()

def main():
    try:
        #server setup
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        server.bind(('localhost', 8080))

        server.listen()
        print("Server is listening on port 8080...")

        server.settimeout(1.0)

        while True:
            try:
                #thread creations
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
    except ConnectionResetError:
        print("A client forcibly disconnected")
    except KeyboardInterrupt:
        print("Shutting down server...")

if __name__ == "__main__":
    main()