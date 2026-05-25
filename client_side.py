import socket
import json
import threading

from classes import *

#Global variables
SERVER_LOCATION = "localhost"
SERVER_PORT = 8080
SERVER_NAME = "server"
RECV_SIZE = 4096
DATA_SIZE = 768 #even though the max transmit length is 1024 base64 encoding makes it 4/3 times longer thus why the data size is 768
TIMEOUT_TIME = 30.0

def handle_errors(err_code, data, target, sender): #creates an operation_variable object and sends it back
    response = error_message()
    response.err_code = err_code
    response.data = data
    response.target = target
    response.sender = sender
    return response

def handle_operation(err_code, target, sender, message): #creates an operation_variable object and sends it back
    response = operation_message()
    response.err_code = err_code
    response.target = target
    response.sender = sender
    response.data = message
    return response

def response_check(answer): #prevents the need to add this code to every option
    if answer['operation_message']['operation_code'] ==  0x2e:
        print("This operation was succsefull")
    elif answer['error_message']:
        print(f"An error occured: {answer['error_message']['data']}")
    elif answer['operation_message']:
        print(f"An unexpected response occured: {answer['operation_message']['data']}")
    else:
        print("And invalid protocol was used by the server")

def handle_input(server_socket, addr):
    pass

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.connect((SERVER_LOCATION, SERVER_PORT))

    #thread for handling input
    thread = threading.Thread(target=handle_input, args=(server,))
    thread.daemon = True
    thread.start()
    
    user_name = None
    option = -1
    response = None
    answer = None

    print("Welcome the the Client Interface for the Internet Relay Chat (IRC) Application!!!")
    user_name = input("Enter the name you want to be idenfited as in the IRC: ")

    while option != 0:
        print("=====Client IRC Interface Options=====")
        print("0. Exit")
        print("1. Connect to server (MUST be done first)")
        print("2. Create a room")
        print("3. Join a room")
        print("4. List members")
        print("5. List rooms")
        print("6. Send a message")
        print("7. Send a file")
        print("8. Disconnect from the server")
        print("9. View messages in inbox")
        is_valid_option = False
        while is_valid_option == False:
            try:
                option = int(input("Enter what you would like to do: "))
                if option < 0 or option > 8:
                    print("Please enter a valid option.")
                    continue
                else:
                    is_valid_option = True
            except Exception as e:
                print("Please enter a valid option.")
                continue
        try:

            if option == 0:
                print("If you exit all stored messages will be lost and you will be disconected from the main server. Meaning your name will no longer be stored on the server.")
                option_check = input("Are you sure you would like to exit (Yes = y | No = n)? ")
                if option_check.lower() != 'y' and option_check.lower() != 'n':
                    while option_check.lower() != 'y' and option_check.lower() != 'n':
                        print("You entred an invalid option")
                        option_check = input("Are you sure you would like to exit (Yes = y | No = n? ")
                if option_check.lower() == 'y':
                    print("Thank you for using this client program. It will now exit...")
                else:
                    print("Good choice! The client program will now continue and you are still connected.")
                    option = -1
            
            elif option == 1:
                response = handle_operation(0x21, SERVER_NAME, user_name, "")
                server.sendall(json.dumps(response).encode('utf-8'))
                server.settimeout(TIMEOUT_TIME)
                try:
                    answer = server.recv(RECV_SIZE)
                    response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")
                finally:
                    server.settimeout(None)

            elif option == 2:
                room_name = input("What is the name of the room you would like to create (must be under 20 charcters): ")
                if len(room_name) > 20 or len(room_name) < 0:
                    while len(room_name) > 20 or len(room_name) < 0:
                        print("You entred an invalid length room name")
                        room_name = input("What is the name of the room you would like to create (must be under 20 charcters): ")
                response = handle_operation(0x21, SERVER_NAME, user_name, room_name)
                server.sendall(json.dumps(response).encode('utf-8'))
                server.settimeout(TIMEOUT_TIME)
                try:
                    answer = server.recv(RECV_SIZE)
                    response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")
                finally:
                    server.settimeout(None)

            elif option == 3:
                room_name = input("What is the name of the room you would like to join (must be under 20 charcters): ")
                if len(room_name) > 20 or len(room_name) < 0:
                    while len(room_name) > 20 or len(room_name) < 0:
                        print("You entred an invalid length room name")
                        room_name = input("What is the name of the room you would like to join (must be under 20 charcters): ")
                response = handle_operation(0x22, SERVER_NAME, user_name, room_name)
                server.sendall(json.dumps(response).encode('utf-8'))
                server.settimeout(TIMEOUT_TIME)
                try:
                    answer = server.recv(RECV_SIZE)
                    response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")
                finally:
                    server.settimeout(None)

            elif option == 4:
                room_name = input("What is the name of the room whose users you would like to see (must be under 20 charcters): ")
                if len(room_name) > 20 or len(room_name) < 0:
                    while len(room_name) > 20 or len(room_name) < 0:
                        print("You entred an invalid length room name")
                        room_name = input("What is the name of the room whose users you would like to see (must be under 20 charcters): ")
                response = handle_operation(0x26, SERVER_NAME, user_name, room_name)
                server.sendall(json.dumps(response).encode('utf-8'))
                server.settimeout(TIMEOUT_TIME)
                try:
                    is_close_message = False
                    print(f"The list of users in room {room_name} are listed below:")
                    while is_close_message != True:
                        answer = server.recv(RECV_SIZE)
                        if answer['message']['operation_message'] == 0x13:
                            print(f"\t{answer['message']['data']}")
                        elif answer['operation_message']['operation_message'] == 0x27:
                            is_close_message = True
                        else:
                            is_close_message = True
                            response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")
                finally:
                    server.settimeout(None)

            elif option == 5:
                response = handle_operation(0x28, SERVER_NAME, user_name, "")
                server.sendall(json.dumps(response).encode('utf-8'))
                server.settimeout(TIMEOUT_TIME)
                try:
                    is_close_message = False
                    print(f"The list of rooms are listed below:")
                    while is_close_message != True:
                        answer = server.recv(RECV_SIZE)
                        if answer['message']['operation_message'] == 0x14:
                            print(f"\t{answer['message']['data']}")
                        elif answer['operation_message']['operation_message'] == 0x29:
                            is_close_message = True
                        else:
                            is_close_message = True
                            response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")
                finally:
                    server.settimeout(None)

            elif option == 6:
                pass

            elif option == 7:
                pass

            elif option == 8:
                pass

            elif option == 9:
                pass

            else:
                print("An unknown error occured. Please enter your option again.")
                continue

        except (BrokenPipeError, ConnectionResetError, OSError) as e: #attempts to catch specfic errors first to avoid catching general erros before moving to the general error catch
            print("The sever seems to be offline. You must reconnect once it comes back online again")
        except Exception as e:
            print(f"Error dealing with the server: {e}")
            print("The sever seems to be offline. You must reconnect once it comes back online again")

    #disconnect operation message sent


    server.close()

if __name__ == "__main__":
    main()