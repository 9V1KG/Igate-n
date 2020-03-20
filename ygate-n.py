# Ygate-n Yaesu igate
# This script is based on the idea from Craig Lamparter
# https://github.com/hessu/ygate
#
# Please modify lines 10 - 18 according to your requirements
# 9V1KG
# Version 2020-03-20
#

USER = "MYCALL-10"  # call sign with SSID
PASS = "00000"  # Passcode for your call sign
LAT = (14, 8.09, "N")   # deg, min
LON = (119, 55.07, "E") # deg, min
BCNTXT = "IGate RF-IS 144.39 - 73"
BEACON = 900  # every 15 min (in sec)
SERIAL = "/dev/ttyUSB0"  # /dev/tty.usbserial-14110 on Mac
HOST = "rotate.aprs2.net"  # tier2 servers round robin
PORT = 14580  # Standard port for aprs server
# BLN1 = f"{USER} iGate up - RF-IS 144.1 MHz QRA: PK04lc" # Bulletin


import os
import socket
import threading
import time
import serial  # pip install
import re
import requests  # pip install
import signal


class Color:
    PURPLE = '\033[1;35;48m'
    CYAN = '\033[1;36;48m'
    BOLD = '\033[1;37;48m'
    BLUE = '\033[1;34;48m'
    GREEN = '\033[1;32;48m'
    YELLOW = '\033[1;33;48m'
    RED = '\033[1;31;48m'
    BLACK = '\033[1;30;48m'
    UNDERLINE = '\033[4;37;48m'
    END = '\033[1;37;0m'


# Define signal handler for ^C (exit program)
def signal_handler(signal, frame):
    print("\r\nCtrl+C, exiting.")
    ser.close()
    os._exit(0)


def format_position(lon, lat):
    # Formatted APRS Position String
    lon = "{:03d}".format(lon[0]) + "{:05.2f}".format(lon[1]) + lon[2]
    lat = "{:02d}".format(lat[0]) + "{:05.2f}".format(lat[1]) + lat[2]
    pos = f'{lat}/{lon}'
    return pos


def is_internet(url='http://www.google.com/', timeout=20):
    try:
        req = requests.get(url, timeout=timeout)
        # HTTP errors are not raised by default, this statement does that
        req.raise_for_status()
        return True
    except requests.HTTPError as e:
        print(f'{Color.RED}Internet connection failed, status code {e.response.status_code}{Color.END}')
        return False
    except requests.ConnectionError:
        return False


def aprs_con():  # Connect to APRS-IS server
    global sck  # socket
    l_time = time.strftime("%H:%M:%S")
    try:
        sck.gettimeout()
    except socket.timeout:
        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # open socket
        sck.settimeout(None)
    try:
        sck.connect((HOST, PORT))
    except OSError as msg:
        print(f'{l_time} {Color.RED}Unable to connect to APRS-IS server.{Color.END} {msg}')
        return False
    sck.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sck.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 512)  # buffer size
    sock_file = sck.makefile(mode='r', buffering=512)
    time.sleep(2)
    # Login to APRS Server
    sck.sendall(bytes(f'user {USER} pass {PASS} vers ygate-n 0.5\n', "ascii"))
    print(f'{l_time}  {Color.GREEN}{sock_file.readline().strip()}{Color.END}')
    print(f'{l_time}  {Color.GREEN}{sock_file.readline().strip()}{Color.END}')
    return True


def send_aprs(aprs_string):
    global sck
    l_time = time.strftime("%H:%M:%S")
    try:
        sck.sendall(bytes(aprs_string, "ascii"))
        print(f'{l_time} {Color.BLUE}{aprs_string.strip()}{Color.END}')
    except TimeoutError or BrokenPipeError or OSError as msg:
        print(f'{l_time} {Color.YELLOW}Connection to APRS server lost, nothing sent{Color.END} {msg}')
        time.sleep(2)
        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if aprs_con():
            sck.sendall(bytes(aprs_string, "ascii"))
            print(f'{l_time} {Color.BLUE}{aprs_string.strip()}{Color.END}')
        else:
            print(f'{l_time} {Color.YELLOW}No internet, not sent: {aprs_string.strip()}{Color.END}')


def send_my_position():  # thread that sends position every BEACON sec to APRS IS
    threading.Timer(BEACON, send_my_position).start()
    position_string = f'{USER}>APRS,TCPIP*:={POSITION}#{BCNTXT}\n'
    send_aprs(position_string)


def send_bulletin():  # Bulletin
    threading.Timer(3600, send_bulletin).start()  # hourly
    bulletin = f'{USER}>APRS,TCPIP*::BLN1     :{BLN1}\n'
    send_aprs(bulletin)


def open_serial():
    try:
        # open first usb serial port
        ser = serial.Serial( SERIAL, 9600)
        return ser
    except:
        print(Color.RED + "Serial interface cannot be initialized" + Color.END)
        print(Color.RED + "Check connection and driver name" + Color.END)
        os._exit(0)

# Main program


signal.signal(signal.SIGINT, signal_handler)

loc_time = time.strftime("%H:%M:%S")
loc_date = time.strftime("%y-%m-%d")
print(f'{Color.GREEN}{loc_date} {USER} IGgate started - Program by 9V1KG{Color.END}')

POSITION = format_position(LON, LAT)  # get APRS position string
print(f'         Position: {POSITION}')

ser = open_serial()
sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # open socket
if is_internet():  # check internet connection
    print(f'{loc_time} Logging in to {HOST}')
    if aprs_con():
        send_my_position()
        # send_bulletin() optional
    else:
        print(f'{loc_time} {Color.YELLOW}No connection to APRS server{Color.END}')
else:
    print(f'{loc_time} {Color.RED}No internet available{Color.END}')
    ser.close()
    os._exit(0)

message = ""
while True:
    b_read = ser.read_until()
    line = b_read.decode("ascii").strip('\n\r')
    # print(f'{Color.PURPLE}{line}{Color.END}')  # debug only
    if re.search(' \[.*\] <UI.*>:', line):  # contains " [date time] <UI *>"
        localtime = time.strftime("%H:%M:%S")
        routing = line
        # replace "[...]<...>" with ",qAR,Call:"
        routing = re.sub(' \[.*\] <UI.*>:', f',qAR,{USER}:', routing)
        # next non-empty line is the payload
        b_read = ser.read_until()
        try:
            payload = b_read.decode("ascii").strip('\n\r')
            packet = bytes(routing + payload + '\r\n', 'ascii')  # byte string
        except UnicodeDecodeError as msg:
            print(f'{localtime} {Color.YELLOW}DecodeError: {routing}{Color.END}')
            print(f'         {msg}:')
            print(f'         {b_read}')
            packet = bytes(routing,'ascii') + b_read  # byte string
            payload = " "
        if len(payload) == 0:
            message = "No Payload, not gated"
        elif re.search(',TCP', routing):  # drop packets sourced from internet
            message = "Internet packet not gated"
        elif re.search('^}.*,TCP.*:', payload):  # drop packets sourced from internet in third party packets
            message = "Internet packet not gated"
        elif 'RFONLY' in routing:
            message = "RFONLY, not gated"
        elif 'NOGATE' in routing:
            message = "NOGATE, not gated"
        else:
            message = f'{packet}'[2:-5]  # no b' and \r\n
            try:
                sck.sendall(packet)  # spec calls for cr/lf, just lf worked in practice too
                print(f'{localtime} {message}')
                message = ""
            except TimeoutError or BrokenPipeError or OSError:
                sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # open socket
                if aprs_con():  # try to reconnect
                    sck.sendall(bytes(packet))
                    print(f'{localtime} {message}')
                    message = ""
                else:
                    message = "No network/internet, not gated"
        if len(message) > 0:
            print(f'{localtime} {Color.YELLOW}{message}: ' + f'{packet}'[2:-5] + Color.END)
