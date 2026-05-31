# IRC Chat Application

A custom Internet Relay Chat (IRC) application built on a purpose-designed protocol over TCP/IP. Clients can connect to a server, create and join rooms, send messages and files, and list members or rooms — with support for private messaging, secure messaging, and file transfer.

> **Note:** This README was made by giving my IRC specfication doc to Claude and having it generate a README. However the content should be the same as the IRC specficatino document.

> **Note:** This project is implemented in Python. To support encryption, the `cryptography` library is required. Before running the code, please install it with (the "--target ." is for local installation only):
> ```
> pip install -r requirements.txt --target .
> ```

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Basic Information](#2-basic-information)
3. [Conventions](#3-conventions)
4. [Message Infrastructure](#4-message-infrastructure)
   - [4.1 Generic Message Format](#41-generic-message-format)
   - [4.2 Operation Messages](#42-operation-messages)
   - [4.3 Error Messages](#43-error-messages)
   - [4.4 Global Message Restrictions](#44-global-message-restrictions)
5. [Client Messages](#5-client-messages)
   - [5.1 Connecting to the Server](#51-connecting-to-the-server)
   - [5.2 Create a Room](#52-create-a-room)
   - [5.3 Join a Room](#53-join-a-room)
   - [5.4 Leave a Room](#54-leave-a-room)
   - [5.5 Disconnect from the Server](#55-disconnect-from-the-server)
   - [5.6 Send a Message](#56-send-a-message)
   - [5.7 Send a File](#57-send-a-file)
6. [Server Messages](#6-server-messages)
   - [6.1 List Members](#61-list-members)
   - [6.2 List Rooms](#62-list-rooms)
   - [6.3 Success](#63-success)
7. [Error Handling](#7-error-handling)
8. [Extra Functionality](#8-extra-functionality)
   - [8.1 Private Messaging](#81-private-messaging)
   - [8.2 Secure Messaging](#82-secure-messaging)
   - [8.3 File Transfer](#83-file-transfer)
   - [8.4 Cloud Connected Server](#84-cloud-connected-server)
9. [Security](#9-security)
10. [Conclusion and Future Directions](#10-conclusion-and-future-directions)

---

## 1. Introduction

This document outlines the scope of a custom Internet Relay Chat (IRC) application and protocol. Clients can join a server and choose to connect, create, or leave different rooms, as well as send messages to everyone in a group. They can also list members of a room or list the available rooms. Additional functionality includes private messaging, secure messaging, file transfer, and a central cloud-connected server.

The foundation of this application is a custom protocol that enables the IRC application to work correctly and effectively using TCP, IP, and Sockets. This document outlines not only the feature set and implementation details, but also the custom protocol used to support them.

---

## 2. Basic Information

All communication outlined in this document takes place over **TCP/IP**. The server will have an open port (e.g., `3000`) that is always listening for incoming requests from the client. Once the first request is sent from the client, it opens a connection, starting a two-way gateway between the server and client. Both are free to send messages at any time.

Every message from the client to the server will warrant a response if it reaches the server successfully — either a success message or an error providing information on the problem. Either end may terminate the connection, although this is primarily handled by the client. The server will only terminate a connection in the case of a timeout.

Client messages must contain information in the header about the receivers, the message type, and the message content. Even messages transferred as part of a stream (e.g., file transfer) must include this header information. The server's response messages will include the user ID/name of the message receiver as well as the message itself.

The client controls their own actions within the server; however, the server is responsible for executing commands, preventing unauthorized or incorrect operations, and enforcing this protocol.

---

## 3. Conventions

- All hexadecimal values in this document are represented with the `0x` prefix (e.g., `0x21`).
- All **name fields** refer to a unique identifier string that is unique to a specific room or client, and is **20 characters or fewer**.
- Any field described as **empty** means the field will exist but will not contain any data.

---

## 4. Message Infrastructure

### 4.1 Generic Message Format

#### 4.1.1 Message Format

```python
class header:
    def __init__(self):
        self.operation_code = 0x00
        self.length = 1024
        self.target = ""
        self.sender = ""

class message:
    def __init__(self):
        self.header = header()
        self.data = bytearray()
```

#### 4.1.2 Definitions

| Field | Description |
|---|---|
| `header.operation_code` | Specifies the type of message being sent within the payload |
| `header.length` | Number of bytes of payload following the header (header not included) |
| `header.target` | The targeted client for this message |
| `header.sender` | The name of the person who originally sent the message |
| `message.header` | How the header is stored within the main message body |
| `message.data` | A byte array storing the message as a byte stream; the client interprets this as either a text message or a file stream depending on the message type |

#### 4.1.3 Operation Codes (`header.operation_code`)

| Code Name | Code Hex |
|---|---|
| `MSG_IN_PROG` | `0x11` |
| `FILE_IN_PROG` | `0x12` |
| `USERS_IN_PROG` | `0x13` |
| `ROOMS_IN_PROG` | `0x14` |

#### 4.1.4 Restrictions

- Data length must be in the range of **1 byte to 1024 bytes**.
- An operation message (see [Section 4.2](#42-operation-messages)) must be sent to indicate the beginning of a data transmission, and another operation message must be sent afterwards to signal completion.
- It is up to the client to parse the byte array into either a string message or a file.

---

### 4.2 Operation Messages

#### 4.2.1 Message Format

```python
class operation_message:
    def __init__(self):
        self.operation_code = 0x00
        self.data = ""
        self.target = ""
        self.sender = ""
```

#### 4.2.2 Definitions

| Field | Description |
|---|---|
| `operation_message.operation_code` | The hex code of the operation this message is conveying |
| `operation_message.data` | Any data required for the operation to occur (some operations leave this empty) |
| `operation_message.target` | The targeted user or group of this operation message |
| `operation_message.sender` | The individual sender of this operation message |

#### 4.2.3 Operation Codes (`operation_message.operation_code`)

| Code Name | Data Requirements | Code Hex |
|---|---|---|
| `CONNECT_TO_SERVER` | Client name | `0x21` |
| `CREATE_ROOM` | Room name | `0x22` |
| `JOIN_ROOM` | Room name | `0x23` |
| `LEAVE_ROOM` | Room name | `0x24` |
| `DISCONNECT` | — | `0x25` |
| `LIST_MEMBERS_OPEN` | Room name | `0x26` |
| `LIST_MEMBERS_CLOSE` | Room name | `0x27` |
| `LIST_ROOMS_OPEN` | — | `0x28` |
| `LIST_ROOMS_CLOSE` | — | `0x29` |
| `SEND_MSG_OPEN` | — | `0x2a` |
| `SEND_MSG_CLOSE` | — | `0x2b` |
| `SEND_FILE_OPEN` | File name | `0x2c` |
| `SEND_FILE_CLOSE` | — | `0x2d` |
| `SUCCESS` | — | `0x2e` |

#### 4.2.4 Restrictions

- Operations that have an **open** and a **close** are intended to send messages in between those two operation signals.
- Operations with an open/close pair have a **30-second timeout timer**. If no close signal or message is received within 30 seconds, the operation automatically times out and sends a timeout error (see [Section 4.3](#43-error-messages)).
- Operation messages that do not require data will leave that field empty.

---

### 4.3 Error Messages

#### 4.3.1 Message Format

```python
class error_message:
    def __init__(self):
        self.err_code = 0x00
        self.data = ""
        self.target = ""
        self.sender = ""
```

#### 4.3.2 Definitions

| Field | Description |
|---|---|
| `error_message.err_code` | The hex code of the error this message is conveying |
| `error_message.data` | Data about the error, often used for display on the client; may be empty if the client is sending the error |
| `error_message.target` | The targeted user or group of this error message |
| `error_message.sender` | The individual sender of this error message |

#### 4.3.3 Error Codes (`error_message.err_code`)

| Code Name | Error Message | Code Hex |
|---|---|---|
| `SERVER_NOT_FOUND` | The server was not found | `0x31` |
| `CLIENT_NOT_FOUND` | The client was not found | `0x32` |
| `NAME_EXISTS` | This name is already taken | `0x33` |
| `INVALID_NAME` | This name is invalid | `0x34` |
| `TIMEOUT_ERROR` | Client timed out due to inactivity | `0x35` |
| `INVALID_OPERATION` | An invalid operation was attempted | `0x36` |
| `INVALID_PROTOCOL` | An incorrect protocol was used | `0x37` |
| `INVALID_ROOM` | The room listed does not exist | `0x38` |
| `INVALID_CLIENT` | The client listed does not exist | `0x39` |
| `ILLEGAL_LENGTH` | The length of the data is wrong | `0x3a` |
| `TOO_MANY_USERS` | There are too many users | `0x3b` |
| `TOO_MANY_ROOMS` | There are too many rooms | `0x3c` |
| `UNKNOWN_ERR` | An unknown error occurred | `0x3d` |

#### 4.3.4 Restrictions

- Error messages do **not** automatically disconnect the connection between the client and server.
- Error messages indicate that an action was not correctly performed or completed.
- Any cleanup actions (e.g., removing partially downloaded files) are the responsibility of the client receiving the error.

---

### 4.4 Global Message Restrictions

- No group or user can be named `"server"`.
- All names for groups and users must be **unique** and **20 characters or fewer**.
- Every message must include one of its valid operation codes.
- If any of these restrictions are violated, the corresponding error code must be sent to the client.
- If more than **100 clients** are connected, error `0x3b` (`TOO_MANY_USERS`) is sent.
- If more than **100 rooms** are created, error `0x3c` (`TOO_MANY_ROOMS`) is sent.

---

## 5. Client Messages

### 5.0.1 General Global Guidelines

- Every client action will warrant a response from the server of either a success (`0x2e`) or an error message. If no response is received, the action can be assumed to have not completed.
- The `sender` field in all definitions is replaced with the actual client name.
- The `data` field is replaced with the actual data being sent.
- When the server is described as completing functionality in the usage sections, this assumes the absence of errors.
- When receiving data it will check for “TCP Message Coalescing” by checking for multiple message separated by the `\n` delimiter character between messages

---

### 5.1 Connecting to the Server

#### Definition

```python
msg = operation_message()
msg.operation_code = 0x21
msg.target = "server"
msg.sender = "client"
msg.data = "client_socket"
```

#### Usage

To initially connect to the server, the client sends a message with the `0x21` operation code. The `sender` field becomes the name the server stores for this user. The clients socket comes in the data.

---

### 5.2 Create a Room

#### Definition

```python
msg = operation_message()
msg.operation_code = 0x22
msg.target = "server"
msg.sender = "client"
msg.data = "room_name"
```

#### Usage

To create a room, the client sends a message with the `0x22` operation code and the desired `room_name`. The server creates the room unless an error prevents the operation.

---

### 5.3 Join a Room

#### Definition

```python
msg = operation_message()
msg.operation_code = 0x23
msg.target = "server"
msg.sender = "client"
msg.data = "room_name"
```

#### Usage

To join a room, the client sends a message with the `0x23` operation code and the `room_name`. The server adds the user to the room.

---

### 5.4 Leave a Room

#### Definition

```python
msg = operation_message()
msg.operation_code = 0x24
msg.target = "server"
msg.sender = "client"
msg.data = "room_name"
```

#### Usage

To leave a room, the client sends a message with the `0x24` operation code and the `room_name`. The server removes the user from the room.

---

### 5.5 Disconnect from the Server

#### Definition

```python
msg = operation_message()
msg.operation_code = 0x25
msg.target = "server"
msg.sender = "client"
```

#### Usage

To disconnect from the server, the client sends a message with the `0x25` operation code. The server then closes the connection with that client.

---

### 5.6 Send a Message

#### Definition

```python
msg = operation_message()
msg.operation_code = 0x2a
msg.target = "group_or_person_name"
msg.sender = "client"
```

#### Usage

To send a message to a group or a specific person:

1. The client sends an operation message with code `0x2a` (`SEND_MSG_OPEN`), specifying the target.
2. The client sends the message content in one or more general message chunks, depending on the size.
3. The client sends a closing operation message with code `0x2b` (`SEND_MSG_CLOSE`) to signal completion.

The server echoes the messages to everyone specified in the original open operation message.

> If the server does not receive a message or a close operation within **30 seconds** of the stream being opened, the operation times out and an error is sent to the relevant users.

---

### 5.7 Send a File

#### Definition

```python
msg = operation_message()
msg.operation_code = 0x2c
msg.target = "group_or_person_name"
msg.sender = "client"
```

#### Usage

To send a file to a group or a specific person:

1. The client sends an operation message with code `0x2c` (`SEND_FILE_OPEN`), specifying the target.
2. The client sends the file data in one or more general message chunks, depending on the file size.
3. The client sends a closing operation message with code `0x2d` (`SEND_FILE_CLOSE`) to signal completion.

The server echoes the file data chunks to everyone specified in the original open operation message.

> If the server does not receive a message or a close operation within **30 seconds** of the stream being opened, the operation times out and an error is sent to the relevant users.

---

## 6. Server Messages

### 6.0.1 General Global Guidelines

- Every server action will warrant a response from the client of either a success (`0x2e`) or an error message. If no response is received, the action can be assumed to have not completed.
- The `sender` field in all definitions is replaced with the server name.
- The `data` field is replaced with the actual data being sent.
- When the server or client is described as completing functionality in the usage sections, this assumes the absence of errors.
- When sending data the server will prevent “TCP Message Coalescing” by adding a `\n` delimiter character after each message

---

### 6.1 List Members

#### Definition

```python
msg = operation_message()
msg.operation_code = 0x27
msg.target = "client"
msg.sender = "server"
```

#### Usage

After receiving a `LIST_MEMBERS_OPEN` (`0x26`) operation from a client, the server:

1. Begins sending back general messages containing the names of the members in the room.
2. Once all members have been sent, sends a `0x27` (`LIST_MEMBERS_CLOSE`) operation to indicate the stream is complete.

---

### 6.2 List Rooms

#### Definition

```python
msg = operation_message()
msg.operation_code = 0x29
msg.target = "client"
msg.sender = "server"
```

#### Usage

After receiving a `LIST_ROOMS_OPEN` (`0x28`) operation from a client, the server:

1. Begins sending back general messages containing the names of all active rooms.
2. Once all rooms have been sent, sends a `0x29` (`LIST_ROOMS_CLOSE`) operation to indicate the stream is complete.

---

### 6.3 Success

#### Definition

```python
msg = operation_message()
msg.operation_code = 0x2e
msg.target = "client"
msg.sender = "server"
```

#### Usage

When an operation completes successfully and no data response is required, the server sends a `0x2e` success response to inform the client that whatever was sent was successfully received and processed.

---

## 7. Error Handling

Both the server and the client are expected to detect and handle errors. Both applications implement robust error handling that falls into one of the error classes defined in [Section 4.3](#43-error-messages). When an error occurs, either the client or server sends an error message to the other party.

Because every message expects a response, lost messages are the primary risk. To address this, every action has a defined expected response time. If a message is not received within that timeframe, another error message is sent — which again expects a response. The specific timeout windows are defined throughout this document wherever they apply.

---

## 8. Extra Functionality

The sections below provide a high-level overview of how the extra features are implemented. The core architecture is designed to support all of them without significant structural changes.

### 8.1 Private Messaging

The server enforces that room names and client names are always unique across both namespaces. When a target name is specified, the server searches both the room list and the client list and delivers the message to the appropriate recipient. With both counts capped at 100, this lookup will never exceed 200 comparisons.

### 8.2 Secure Messaging

This feature requires no changes to the message structure. Each end uses a shared encryption library to encrypt and decrypt messages. The server decrypts incoming messages and re-encrypts them before forwarding to another client, who then decrypts using the same library. No additional architecture is needed to support this.

### 8.3 File Transfer

An operation message pair (`SEND_FILE_OPEN` / `SEND_FILE_CLOSE`) was added specifically to signal file transfers. Since `message.data` is a bytearray rather than a string, any binary data — whether file content or text — can be transmitted using the same general message structure. The receiving client, having received the open operation, knows to treat the incoming data as a file.

---

## 9. Security

Security is handled through end-to-end encryption implemented at the client level using a dedicated encryption library. Any message intercepted in transit will appear as encrypted bytes and is not practically decipherable without the correct key.

---

## 10. Conclusion and Future Directions

This document provides clear and in-depth documentation of the IRC application and its protocol, covering the full architecture and how each component contributes to the overall feature set.

The architecture is designed to be modular, making it straightforward to extend the protocol with new features in the future. While this protocol is specifically designed for the feature set described here, the modular design means future additions can be implemented with minimal disruption to the existing structure.