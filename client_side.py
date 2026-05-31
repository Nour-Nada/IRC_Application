import socket
import json
import threading
import datetime
import time
import queue
import sys
import ssl
from datetime import timedelta
from pathlib import Path
import atexit

from cryptography.fernet import Fernet # MUST DO: "pip install cryptograhy" or "pip install -r requirements.txt"

from classes import *

#Global variables
SERVER_LOCATION = "localhost"
SERVER_PORT = 8080
SERVER_NAME = "server"
RECV_SIZE = 4096
DATA_SIZE = 768 #even though the max transmit length is 1024 base64 encoding makes it 4/3 times longer thus why the data size is 768
TIMEOUT_TIME = 30.0

# Shared variable that allows the thread to put in answers from functions that occure
server_answer = queue.Queue(maxsize=50) #makes the receviving structure for messages from the server stack in a queue. The reason the max size is 10 is stop any messages that are not being poped from corrupting the program
#signals to the thread and main wheter the connection is lost or not
connection_lost = False
connection_lost_lock = threading.Lock()

#user inbox
inbox = {}
inbox_lock = threading.Lock()
inbox_counter = 0

#in progress incoming messages (they are stored like this since techinically many users can send something at the same time)
in_prog = {} #Format: (sender, target): "data"
in_prog_lock = threading.Lock()

#Encryption variables
key = "qbGdttxtbJcJaPeFildKgl1tpx0iaYM5w5ssHhrgPJA=" #hardcoded for now but could be made dynamic
cipher_suite = Fernet(key)


class recv_message: #class for storing received messages
    def __init__(self, time, prog_message, is_it_file):
        self.time_recv = time
        self.message = prog_message
        self.is_file = is_it_file
        self.is_valid = True #just indicates wheter the message was saved or not since some message may have duplicate file names

def handle_errors(err_code, data, target, sender): #creates an operation_variable object and sends it back
    response = error_message()
    response.err_code = err_code
    response.data = data
    response.target = target
    response.sender = sender
    return response

def handle_operation(code, target, sender, message): #creates an operation_variable object and sends it back
    response = operation_message()
    response.operation_code = code
    response.target = target
    response.sender = sender
    response.data = message
    return response

def response_check(answer, to_print=True): #prevents the need to add this code to every option
    if 'operation_message' in answer and answer['operation_message']['operation_code'] ==  0x2e:
        if to_print: print("This operation was succsefull")
        return True
    elif 'error_message' in answer and answer['error_message']:
        if to_print: print(f"An error occured: {answer['error_message']['data']}")
        return False
    elif 'operation_message' in answer and answer['operation_message']:
        if to_print: print(f"An unexpected response occured: {answer['operation_message']['operation_code']}")
        return False
    else:
        if to_print: print("An unknown error occured")
        return False

def timeout_check(): #since I'm using a thread to capture all incoming traffic including that not realted to the current message I sent, I can't use the standard timeout. Thus I have to make my own makeshift one
    global server_answer
    
    answer = None
    target_time = datetime.datetime.now() + datetime.timedelta(seconds=TIMEOUT_TIME)
    while server_answer.empty() == True and datetime.datetime.now() < target_time:
        time.sleep(0.01)
    if datetime.datetime.now() > target_time:
        raise socket.timeout
    else:
        answer = server_answer.get()
        return answer

def handle_input(server_socket): #the thread that process all the messages comng from the server
    global connection_lost
    global connection_lost_lock
    global server_answer
    global in_prog
    global in_prog_lock
    global inbox
    global inbox_lock
    global inbox_counter

    while connection_lost == False:
        while connection_lost == False:
            try:
                undecrypt_tmp_answer = server_socket.recv(RECV_SIZE)
                # print(f"{undecrypt_tmp_answer}") #for testing purposes
                tmp_list = undecrypt_tmp_answer.split(b"\n") #splits the messages based on delimters to prevent errors with TCP messages that combine together
                # print(f"{tmp_list}") #for testing purposes

                for tmp_answer in tmp_list:
                    if len(tmp_answer) == 0: continue
                    tmp_ret = cipher_suite.decrypt(tmp_answer).decode('utf-8')
                    parsed_data = json.loads(tmp_ret)
                    # print(f"{tmp_ret}") #for testing purposes

                    if ('operation_message' in parsed_data and parsed_data['operation_message']['sender'] == SERVER_NAME) or ('error_message' in parsed_data and parsed_data['error_message']['sender'] == SERVER_NAME) or ('message' in parsed_data and parsed_data['message']['header']['sender'] == SERVER_NAME):
                        server_answer.put(parsed_data)
                    else:
                        new_message = None
                        if 'message' in parsed_data:
                            pair_key = (parsed_data['message']['header']['sender'], parsed_data['message']['header']['target'])
                            if pair_key not in in_prog:
                                print("The message byte does not belong to any prexisitng message, or a timeout occured", file=sys.stderr)
                            elif parsed_data['message']['header']['operation_code'] == 0x11:
                                in_prog[pair_key].message += parsed_data['message']['data']
                                in_prog[pair_key].time_recv = datetime.datetime.now()
                            elif parsed_data['message']['header']['operation_code'] == 0x12:
                                if in_prog[pair_key].is_valid == True:
                                    file_name = in_prog[pair_key].message
                                    in_prog[pair_key].time_recv = datetime.datetime.now()
                                    data = base64.b64decode(parsed_data['message']['data'])
                                    with open(file_name, "ab") as file:
                                        file.write(data)
                            else:
                                print("An incorrect protocol was used", file=sys.stderr)
                        elif 'operation_message' in parsed_data:
                            if parsed_data['operation_message']['operation_code'] == 0x2a: #creates the message
                                with in_prog_lock:
                                    in_prog[(parsed_data['operation_message']['sender'], parsed_data['operation_message']['target'])] = recv_message(datetime.datetime.now(), "", False)
                            elif parsed_data['operation_message']['operation_code'] == 0x2b: #moves the message from the in progress structure to the inbox
                                with in_prog_lock:
                                    new_message = in_prog[(parsed_data['operation_message']['sender'], parsed_data['operation_message']['target'])]
                                    del in_prog[(parsed_data['operation_message']['sender'], parsed_data['operation_message']['target'])]
                                with inbox_lock:
                                    inbox[(parsed_data['operation_message']['sender'], parsed_data['operation_message']['target'], inbox_counter)] = new_message
                                inbox_counter += 1
                            elif parsed_data['operation_message']['operation_code'] == 0x2c:
                                file_path = Path(parsed_data['operation_message']['data'])
                                with in_prog_lock:
                                        in_prog[(parsed_data['operation_message']['sender'], parsed_data['operation_message']['target'])] = recv_message(datetime.datetime.now(), parsed_data['operation_message']['data'], True)
                                if file_path.is_file():
                                    in_prog[(parsed_data['operation_message']['sender'], parsed_data['operation_message']['target'])].is_valid = False #sets messages with files that already exist as not valid message streams
                            elif parsed_data['operation_message']['operation_code'] == 0x2d:
                                with in_prog_lock:
                                    new_message = in_prog[(parsed_data['operation_message']['sender'], parsed_data['operation_message']['target'])]
                                    del in_prog[(parsed_data['operation_message']['sender'], parsed_data['operation_message']['target'])]
                                with inbox_lock:
                                    inbox[(parsed_data['operation_message']['sender'], parsed_data['operation_message']['target'], inbox_counter)] = new_message
                                inbox_counter += 1
                            else:
                                print("An incorrect protocol was used", file=sys.stderr)
                        else:
                            print("An incorrect protocol was used", file=sys.stderr)
            except ConnectionResetError as e: #attempts to catch specfic errors first to avoid catching general errors before moving to the general error catch
                print(f"\nThe server was forcibly closed.")
                print("Exit what you are currently in then choose option 1 to reconnect:")
                with connection_lost_lock:
                    connection_lost = True
            except (BrokenPipeError, ConnectionResetError, OSError) as e: #attempts to catch specfic errors first to avoid catching general erros before moving to the general error catch
                print("The connection between the server and client has ended")
                with connection_lost_lock:
                    connection_lost = True
            except Exception as e:
                print(f"\nAn unexpected error occured: {e}")
                with connection_lost_lock:
                    connection_lost = True

def track_time_in_prog(): #this thread removes any message that are being transmitted in progress but passed the 30 second timer limit
    global in_prog
    global in_prog_lock
    while True:
        time.sleep(1.0)
        while len(in_prog) != 0:
            time.sleep(1.0)
            with in_prog_lock:
                keys_to_delete = list(in_prog.keys())
                for x in keys_to_delete:
                    if x in in_prog:
                        if datetime.datetime.now() - in_prog[x].time_recv > timedelta(seconds=TIMEOUT_TIME):
                            if in_prog[x].is_file == True: #deletes files that were not fully uploaded
                                Path(in_prog[x].message).unlink(missing_ok=True)
                            del in_prog[x]
                        else:
                            continue
            

def main():
    global connection_lost
    global connection_lost_lock

    user_name = None
    option = -1
    response = None
    answer = None

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        server.connect((SERVER_LOCATION, SERVER_PORT))
        #thread for handling input
        thread1 = threading.Thread(target=handle_input, args=(server,)) 
        thread1.daemon = True
        thread1.start()
        #thread for ensuring encoming message don't timeout
        thread2 = threading.Thread(target=track_time_in_prog, args=())
        thread2.daemon = True
        thread2.start()

        atexit.register(thread1.join, 0.2)
        atexit.register(thread2.join, 0.2)
    except Exception as e:
        print("The server could not be connected to. You must do option 1 and attempt to recconect.")

    if option != 0:
        print("Welcome the the Client Interface for the Internet Relay Chat (IRC) Application!!!")
        user_name = input("Enter the name you want to be idenfited as in the IRC: ")

    while option != 0: #the GUI for completing commands
        print("\n=====Client IRC Interface Options=====")
        print("0. Exit")
        print("1. Connect to server or Reconnect(MUST be done first)")
        print("2. Create a room")
        print("3. Join a room")
        print("4. Leave a Room")
        print("5. List members")
        print("6. List rooms")
        print("7. Send a message")
        print("8. Send a file")
        print("9. Disconnect from the server")
        print("10. View messages in inbox")
        is_valid_option = False
        while is_valid_option == False: #makes sure the option we proceed with is valid
            try:
                option = int(input("Enter what you would like to do: "))
                if option < 0 or option > 10:
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
                    response = handle_operation(0x25, SERVER_NAME, user_name, "")
                    server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                    try:
                        answer = timeout_check()
                        response_check(answer)
                    except socket.timeout:
                        print("The opearation was not completed due to a timeout")
                else:
                    print("Good choice! The client program will now continue and you are still connected.")
                    option = -1
            
            elif option == 1:
                if connection_lost == True: #attempts to restablish the connection although it may not work
                    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    server.connect((SERVER_LOCATION, SERVER_PORT))
                    with connection_lost_lock:
                        connection_lost = False
                    thread1 = threading.Thread(target=handle_input, args=(server,))
                    thread1.daemon = True
                    thread1.start()
                response = handle_operation(0x21, SERVER_NAME, user_name, user_name)
                server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                try:
                    answer = timeout_check()
                    response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")

            elif option == 2:
                room_name = input("What is the name of the room you would like to create (must be under 20 charcters): ")
                if len(room_name) > 20 or len(room_name) <= 0:
                    while len(room_name) > 20 or len(room_name) <= 0:
                        print("You entred an invalid length room name")
                        room_name = input("What is the name of the room you would like to create (must be under 20 charcters): ")
                response = handle_operation(0x22, SERVER_NAME, user_name, room_name)
                server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                try:
                    answer = timeout_check()
                    response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")

            elif option == 3:
                room_name = input("What is the name of the room you would like to join (must be under 20 charcters): ")
                if len(room_name) > 20 or len(room_name) < 0:
                    while len(room_name) > 20 or len(room_name) < 0:
                        print("You entred an invalid length room name")
                        room_name = input("What is the name of the room you would like to join (must be under 20 charcters): ")
                response = handle_operation(0x23, SERVER_NAME, user_name, room_name)
                server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                try:
                    answer = timeout_check()
                    response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")

            elif option == 4:
                room_name = input("What is the name of the room you would like to leave (must be under 20 charcters): ")
                if len(room_name) > 20 or len(room_name) < 0:
                    while len(room_name) > 20 or len(room_name) < 0:
                        print("You entred an invalid length room name")
                        room_name = input("What is the name of the room you would like to leave (must be under 20 charcters): ")
                response = handle_operation(0x24, SERVER_NAME, user_name, room_name)
                server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                try:
                    answer = timeout_check()
                    response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")

            elif option == 5:
                room_name = input("What is the name of the room whose users you would like to see (must be under 20 charcters): ")
                if len(room_name) > 20 or len(room_name) <= 0:
                    while len(room_name) > 20 or len(room_name) <= 0:
                        print("You entred an invalid length room name")
                        room_name = input("What is the name of the room whose users you would like to see (must be under 20 charcters): ")
                response = handle_operation(0x26, SERVER_NAME, user_name, room_name)
                server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                try:
                    #catches the succes message first
                    response_check(answer)
                    is_close_message = False
                    print(f"The list of users in room {room_name} are listed below:")
                    while is_close_message != True:
                        answer = timeout_check()
                        if 'message' in answer and answer['message']['header']['operation_code'] == 0x13:
                            print(f"\t{answer['message']['data']}")
                        elif 'operation_message' in answer and answer['operation_message']['operation_code'] == 0x27:
                            is_close_message = True
                        else:
                            is_close_message = True
                            response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")

            elif option == 6:
                response = handle_operation(0x28, SERVER_NAME, user_name, "")
                server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                try:
                    #catches the succes message first
                    response_check(answer)
                    is_close_message = False
                    print(f"The list of rooms are listed below:")
                    while is_close_message != True:
                        answer = timeout_check()
                        if 'message' in answer and 'message' in answer and answer['message']['header']['operation_code'] == 0x14:
                            print(f"\t{answer['message']['data']}")
                        elif 'operation_message' in answer and answer['operation_message']['operation_code'] == 0x29:
                            is_close_message = True
                        else:
                            is_close_message = True
                            response_check(answer)
                except socket.timeout:
                    print("The opearation was not completed due to a timeout")

            elif option == 7:
                option_check = 'y'
                while option_check.lower() == 'y':
                    index = 0
                    room_name = input("What is the name of the room or user who you would like to send a message to (must be under 20 charcters): ")
                    if len(room_name) > 20 or len(room_name) <= 0 or room_name == user_name:
                        while len(room_name) > 20 or len(room_name) <= 0  or room_name == user_name:
                            if len(room_name) > 20 or len(room_name) <= 0: print("You entred an invalid name length")
                            else: print("You can not send a message to yourself")
                            room_name = input("What is the name of the room or user who you would like to send a message to (must be under 20 charcters): ")

                    #the order for sending this is first sending the opening message, then the contents, then the closing message
                    text_message = input("Enter the message you would like to send below:\n")
                    if len(text_message) <= 0:
                        while len(text_message) <= 0:
                            print("You entred an invalid message length")
                            text_message = input("Enter the message you would like to send below:\n")
                    response = handle_operation(0x2a, room_name, user_name, "")
                    server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                    try:
                        message_not_complete = True
                        answer = timeout_check()
                        check_result = response_check(answer)
                        while message_not_complete and check_result:
                            to_send = None
                            if len(text_message) - index <= DATA_SIZE:
                                to_send = text_message[index:]
                                message_not_complete = False
                            else:
                                to_send = text_message[index:index + DATA_SIZE]
                                index += DATA_SIZE
                            response = message()
                            response.header.operation_code = 0x11
                            response.header.length = 4 * math.ceil(len(to_send) / 3)
                            response.header.target = room_name
                            response.header.sender = user_name
                            response.data = to_send
                            server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                            answer = timeout_check()
                            check_result = response_check(answer, False)
                        if check_result:
                            response = handle_operation(0x2b, room_name, user_name, "")
                            server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                            answer = timeout_check()
                            response_check(answer)
                    except socket.timeout:
                        print("The opearation was not completed due to a timeout")
                    
                    option_check = input("Would you like to send to another room or user (Yes = y | No = n)? ")
                    if option_check.lower() != 'y' and option_check.lower() != 'n':
                        while option_check.lower() != 'y' and option_check.lower() != 'n':
                            print("You entred an invalid option")
                            option_check = input("Would you like to send to another room or user (Yes = y | No = n)? ")

            elif option == 8:
                option_check = 'y'
                while option_check.lower() == 'y':
                    index = 0
                    room_name = input("What is the name of the room or user who you would like to send a file to (must be under 20 charcters): ")
                    if len(room_name) > 20 or len(room_name) <= 0 or room_name == user_name:
                        while len(room_name) > 20 or len(room_name) <= 0  or room_name == user_name:
                            if len(room_name) > 20 or len(room_name) <= 0: print("You entred an invalid name length")
                            else: print("You can not send a file to yourself")
                            room_name = input("What is the name of the room or user who you would like to send a file to (must be under 20 charcters): ")

                    #the order for sending this is first sending the opening message, then the contents, then the closing message
                    print("Any file over a few mb's will probably take minutes due to the arhciture of this IRC")
                    file_name = input("Enter the file you would like to send below: ")
                    if len(file_name) <= 0:
                        while len(file_name) <= 0 and len(file_name) > 20:
                            print("The length of the name is invalid.")
                            file_name = input("Enter the file you would like to send below: ")

                    final_file_name = input("Enter what name you would like to have the file named as upon arrival (must be under 20 charcters): ")
                    if len(file_name) <= 0:
                        while len(final_file_name) <= 0:
                            print("The length of the name is invalid.")
                            final_file_name = input("Enter what name you would like to have the file named as upon arrival (must be under 20 charcters): ")
                    response = handle_operation(0x2c, room_name, user_name, final_file_name)
                    server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                    try:
                        message_not_complete = True
                        answer = timeout_check()
                        check_result = response_check(answer)
                        with open(file_name, "rb") as file:
                            while message_not_complete and check_result:
                                to_send = file.read(DATA_SIZE)
                                if not to_send:            # True when chunk is b'' (EOF reached)
                                    message_not_complete = False
                                    continue
                                response = message()
                                response.header.operation_code = 0x12
                                response.header.length = 4 * math.ceil(len(to_send) / 3)
                                response.header.target = room_name
                                response.header.sender = user_name
                                response.data = to_send
                                server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                                answer = timeout_check()
                                check_result = response_check(answer, False)
                            if check_result:
                                response = handle_operation(0x2d, room_name, user_name, "")
                                server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                                answer = timeout_check()
                                response_check(answer, False)
                    except socket.timeout:
                        print("The opearation was not completed due to a timeout")
                    except FileNotFoundError:
                        print("The file you named does not exist.")
                    
                    option_check = input("Would you like to send to another room or user (Yes = y | No = n)? ")
                    if option_check.lower() != 'y' and option_check.lower() != 'n':
                        while option_check.lower() != 'y' and option_check.lower() != 'n':
                            print("You entred an invalid option")
                            option_check = input("Would you like to send to another room or user (Yes = y | No = n)? ")

            elif option == 9:
                print("If you disconnect all stored data of you on the server will be lost and you will be disconected. Meaning your name will no longer be stored on the server.")
                option_check = input("Are you sure you would like to disconnect (Yes = y | No = n)? ")
                if option_check.lower() != 'y' and option_check.lower() != 'n':
                    while option_check.lower() != 'y' and option_check.lower() != 'n':
                        print("You entred an invalid option")
                        option_check = input("Are you sure you would like to disconnect (Yes = y | No = n? ")
                if option_check.lower() == 'y':
                    print("Thank you for connecting to the server. It will now disconnect...")
                    response = handle_operation(0x25, SERVER_NAME, user_name, "")
                    server.sendall(cipher_suite.encrypt((json.dumps(response.to_dict()) ).encode('utf-8')) + b"\n")
                    try:
                        answer = timeout_check()
                        response_check(answer)
                    except socket.timeout:
                        print("The opearation was not completed due to a timeout")
                else:
                    print("Good choice! The client program will now continue and you are still connected.")
                    option = -1

            elif option == 10:
                print(f"Message Count in Inbox: {len(inbox)}", file=sys.stderr)
                for (sender, target, message_index), msg in inbox.items():
                    if msg.is_file == False:
                        print(f"[{msg.time_recv}] {sender} -> {target}: {msg.message}")
                    else:
                        if msg.is_valid:
                            print(f"[{msg.time_recv}] (is file) {sender} -> {target}; The file name is: {msg.message}")
                        else:
                            print(f"[{msg.time_recv}] {sender} -> {target}: (duplicate file ignored) {msg.message}")

            else:
                print("An unknown error occured. Please enter your option again.")
                continue
        except ConnectionResetError as e: #attempts to catch specfic errors first to avoid catching general erros before moving to the general error catch
            print(f"\nThe server was forcibly closed.")
            print("Exit what you are currently in then choose option 1 to reconnect:")
            with connection_lost_lock:
                connection_lost = True
        except (BrokenPipeError, ConnectionResetError, OSError) as e: #attempts to catch specfic errors first to avoid catching general erros before moving to the general error catch
            print("\nThe sever seems to be offline. You must reconnect once it comes back online again")
            print("Exit what you are currently in then choose option 1 to reconnect:")
            with connection_lost_lock:
                connection_lost = True
        except Exception as e:
            print(f"\nAn unexpected error occured: {e}")
            with connection_lost_lock:
                connection_lost = True


    server.close()
    print("Thank you for using this IRC application :)")

if __name__ == "__main__":
    main()