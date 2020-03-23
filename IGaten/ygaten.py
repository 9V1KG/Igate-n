# Ygate-n Yaesu igate
# This script is based on the idea from Craig Lamparter
# https://github.com/hessu/ygate
#
# 9V1KG
# Version 2020-03-20
#
# DU3/M0FGC
# Slight mods


import os
import socket
import threading
import time
import serial
import re
import requests
import signal


class Color:
    PURPLE = "\033[1;35;48m"
    CYAN = "\033[1;36;48m"
    BOLD = "\033[1;37;48m"
    BLUE = "\033[1;34;48m"
    GREEN = "\033[1;32;48m"
    YELLOW = "\033[1;33;48m"
    RED = "\033[1;31;48m"
    BLACK = "\033[1;30;48m"
    UNDERLINE = "\033[4;37;48m"
    END = "\033[1;37;0m"


class Ygate:

    HOURLY = 3600.0

    def __init__(
        self,
        HOST="rotate.aprs2.net",
        PORT=14580,
        USER="MYCALL-10",
        PASS="00000",
        LAT=(14, 8.09, "N"),
        LON=(119, 55.07, "E"),
        BCNTXT="IGate RF-IS 144.39 - 73",
        BEACON=900.0,
        SERIAL="/dev/ttyUSB0",
    ):
        """
        Class initializer

        :param HOST:
        :param PORT:
        :param USER:
        :param PASS:
        :param LAT:
        :param LON:
        :param BCNTXT:
        :param BEACON:
        :param SERIAL:
        """
        self.PORT = PORT
        self.HOST = HOST
        self.SERIAL = SERIAL
        self.BEACON = BEACON
        self.BCNTXT = BCNTXT
        self.LON = LON
        self.LAT = LAT
        self.PASS = PASS
        self.USER = USER
        self.BLN1 = f"{USER} iGate up - RF-IS 144.1 MHz QRA: PK04lc"  # Bulletin
        self.pos = self.format_position(self.LON, self.LAT)
        self.ser = None
        self.sck = None

    # Define signal handler for ^C (exit program)
    def signal_handler(self, interupt_signal, frame):
        print("\r\nCtrl+C, exiting.")
        self.ser.close()
        os._exit(0)

    def format_position(self, lon: tuple, lat: tuple) -> str:
        """
         # Formatted APRS Position String
        :param lon: Tuple of Degree, Decimal-Minutes, "N or S"
        :param lat: Tuple of Degree, Decimal-Minutes , "E or W"
        :return: Aprs formatted string
        """

        lon = "{:03d}".format(lon[0]) + "{:05.2f}".format(lon[1]) + lon[2]
        lat = "{:02d}".format(lat[0]) + "{:05.2f}".format(lat[1]) + lat[2]
        pos = f"{lat}/{lon}"
        return pos

    def is_internet(
        self, url: str = "http://www.google.com/", timeout: int = 30
    ) -> bool:
        """
        Is there an internet connection
        :param url: String pointing to a URL
        :param timeout: How long we wait in seconds
        :return:
        """
        try:
            req = requests.get(url, timeout=timeout)
            # HTTP errors are not raised by default, this statement does that
            req.raise_for_status()
            return True
        except requests.HTTPError as e:
            print(
                f"{Color.RED}Internet connection failed, status code {e.response.status_code}{Color.END}"
            )
            return False
        except requests.ConnectionError:
            return False

    def aprs_con(self) -> bool:
        """
        Connect to APRS-IS server
        :return: True or False depending on the success.
        """

        l_time = time.strftime("%H:%M:%S")
        try:
            self.sck.gettimeout()
        except socket.timeout:
            self.sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # open socket
            self.sck.settimeout(None)
        try:
            self.sck.connect((self.HOST, self.PORT))
        except OSError as msg:
            print(
                f"{l_time} {Color.RED}Unable to connect to APRS-IS server.{Color.END} {msg}"
            )
            return False
        self.sck.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sck.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 512)  # buffer size
        sock_file = self.sck.makefile(mode="r", buffering=512)
        time.sleep(2)
        # Login to APRS Server
        self.sck.sendall(
            bytes(f"user {self.USER} pass {self.PASS} vers ygate-n 0.5\n", "ascii")
        )
        print(
            f"{l_time}  {Color.GREEN}{sock_file.readline().strip()}{Color.END}"
        )
        # if second line contains "unverified", login was not successful
        login = sock_file.readline().strip()
        print(f"{l_time}  {Color.GREEN}{login}{Color.END}")
        if login.find("unverified") != -1:
            print(
                f"{l_time} {Color.RED}Login not successful. Check call sign and verification code.{Color.END}")
            exit(0)
        else:
            return True

    # todo Add Logging
    def send_aprs(self, aprs_string: str) -> bool:
        """
        Send aprs data
        :param aprs_string:
        :return: Boolean indicating Success or failure
        """
        l_time = time.strftime("%H:%M:%S")
        try:
            self.sck.sendall(bytes(aprs_string, "ascii"))
            print(f"{l_time} {Color.BLUE}{aprs_string.strip()}{Color.END}")
            return True
        except TimeoutError or BrokenPipeError or OSError as msg:
            print(
                f"{l_time} {Color.YELLOW}Connection to APRS server lost{Color.END} {msg}"
            )
            time.sleep(2)
            self.sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.aprs_con():
                self.sck.sendall(bytes(aprs_string, "ascii"))
                print(f"{l_time} {Color.BLUE}{aprs_string.strip()}{Color.END}")
                return True
            else:
                print(
                    f"{l_time} {Color.YELLOW}No internet, not sent: {aprs_string.strip()}{Color.END}"
                )
                return False

    def send_my_position(self):
        """
        thread that sends position every BEACON sec to APRS IS
        """
        position_string = f"{self.USER}>APRS,TCPIP*:={self.pos}#{self.BCNTXT}\n"
        threading.Timer(self.BEACON, self.send_my_position).start()
        try:
            self.send_aprs(position_string)
        except BrokenPipeError as err:
            if self.aprs_con():
                self.send_aprs(position_string)
            else:
                l_t = time.strftime("%H:%M:%S")
                print(f"{l_t} {Color.YELLOW}Cannot connect to APRS server:{Color.END} {str(err)}")

    def send_bulletin(self):
        """
        thread that sends bulletin every HOURLY sec to APRS IS
        """
        bulletin = f"{self.USER}>APRS,TCPIP*::BLN1     :{self.BLN1}\n"
        threading.Timer(self.HOURLY, self.send_bulletin).start()
        try:
            self.send_aprs(bulletin)
        except BrokenPipeError as err:
            if self.aprs_con():
                self.send_aprs(bulletin)
            else:
                l_t = time.strftime("%H:%M:%S")
                print(f"{l_t} {Color.YELLOW}Cannot connect to APRS server:{Color.END} {str(err)}")

    def open_serial(self):
        try:
            # open first usb serial port
            self.ser = serial.Serial(self.SERIAL, 9600)
            return self.ser
        except Exception as err:
            print(" " * 9 + f"{Color.RED}Serial interface cannot be initialized{Color.END}")
            print(" " * 9 + f"{Color.RED}Check connection and driver name{Color.END}")
            # print(Color.RED + f"Error {str(err)}")
            exit(0)

    def start(self):
        signal.signal(signal.SIGINT, self.signal_handler)

        loc_time = time.strftime("%H:%M:%S")
        loc_date = time.strftime("%y-%m-%d")
        print(
            f"{Color.GREEN}{loc_date} {self.USER} IGgate started - Program by 9V1KG{Color.END}"
        )
        print(" "* 9 + f"Position: {self.pos}")

        ser = self.open_serial()
        self.sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # open socket
        if self.is_internet():  # check internet connection
            print(f"{loc_time} Logging in to {self.HOST}")
            if self.aprs_con():
                self.send_my_position()
                self.send_bulletin()
            else:
                print(
                    f"{loc_time} {Color.YELLOW}No connection to APRS server{Color.END}"
                )
        else:
            print(f"{loc_time} {Color.RED}No internet available{Color.END}")
            ser.close()
            exit(0)
        while True:
            b_read = self.ser.read_until()
            line = b_read.decode("ascii").strip("\n\r")
            # print(f'{Color.PURPLE}{line}{Color.END}')  # debug only
            if re.search(" \[.*\] <UI.*>:", line):  # contains " [date time] <UI *>"
                localtime = time.strftime("%H:%M:%S")
                routing = line
                # replace "[...]<...>" with ",qAR,Call:"
                routing = re.sub(" \[.*\] <UI.*>:", f",qAR,{self.USER}:", routing)
                # next non-empty line is the payload
                b_read = self.ser.read_until()
                try:
                    payload = b_read.decode("ascii").strip("\n\r")
                    packet = bytes(routing + payload + "\r\n", "ascii")  # byte string
                except UnicodeDecodeError as msg:
                    print(
                        f"{localtime} {Color.YELLOW}DecodeError: {routing}{Color.END}"
                    )
                    print(f"         {msg}:")
                    print(f"         {b_read}")
                    packet = bytes(routing, "ascii") + b_read  # byte string
                    payload = " "
                if len(payload) == 0:
                    message = "No Payload, not gated"
                elif re.search(",TCP", routing):  # drop packets sourced from internet
                    message = "Internet packet not gated"
                elif re.search(
                    "^}.*,TCP.*:", payload
                ):  # drop packets sourced from internet in third party packets
                    message = "Internet packet not gated"
                elif "RFONLY" in routing:
                    message = "RFONLY, not gated"
                elif "NOGATE" in routing:
                    message = "NOGATE, not gated"
                else:
                    message = f"{packet}"[2:-5]  # no b' and \r\n
                    try:
                        if self.is_internet():
                            self.sck.sendall(
                                packet
                            )  # spec calls for cr/lf, just lf worked in practice too
                            print(f"{localtime} {message}")
                            message = ""
                        else:
                            message = "No Internet, packet not gated"

                    except TimeoutError or BrokenPipeError or OSError:
                        self.sck = socket.socket(
                            socket.AF_INET, socket.SOCK_STREAM
                        )  # open socket
                        if self.aprs_con():  # try to reconnect
                            self.sck.sendall(
                                packet
                            )
                            print(f"{localtime} {message}")
                            message = ""
                        else:
                            message = "No network/internet, not gated"
                if len(message) > 0:
                    print(
                        f"{localtime} {Color.YELLOW}{message}: "
                        + f"{packet}"[2:-5]
                        + Color.END
                    )
"""
igate = Ygate(
    "rotate.aprs2.net",
    14580,
    "MYCALL-10",
    "00000",
    (14, 7.00, "N"),
    (120, 58.00, "E"),
    "IGate RF-IS 144.10 - 73",
    900.0,
    "/dev/ttyUSB0"
)
igate.start()
"""
