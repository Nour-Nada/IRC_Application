import socket
import json

from classes import *

def main():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('localhost', 8080))

if __name__ == "__main__":
    main()