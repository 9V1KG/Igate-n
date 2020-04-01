# Ygate-n Yaesu igate
# This script is based on an idea from Craig Lamparter
# https://github.com/hessu/ygate
#
# 9V1KG Klaus D Goepel -
# https://klsin.bpmsg.com
# https://github.com/9V1KG/Igate-n
#
# DU3/M0FGC
# Slight mods
#
# Version 2020-03-31
#


import os
import re
import signal
import socket
import threading
import time
import math
import serial
from IGaten import Color
from .functions import format_position, is_internet, compress_position


class Ygate:
    HOURLY = 3600.0

    def __init__(
        self,
        USER="MYCALL-10",
        PASS="00000",
        LAT=(14, 5.09, "N"),
        LON=(119, 58.07, "E"),
        ALT=(670.0, "m"),
        SERIAL="/dev/ttyUSB0",
        BCNTXT="IGate RF-IS 144.1 testing phase - 73",
        BEACON=900.0,
        HOST="rotate.aprs2.net",
        PORT=14580,
    ):
        """
        :param USER:   Your callsign with ssid (-10 for igate)
        :param PASS:   Your aprs secret code
        :param LAT:    Latitude
        :param LON:    Longitude
        :param ALT:    Altitude in ft or m, 0. if no altitude
        :param BCNTXT: Beacon text
        :param SERIAL: Driver location for serial interface
        :param BEACON: Beacon frequency in seconds
        :param HOST:   APRS internet server
        :param PORT:   APRS internet server port
        """

        self.PORT = PORT
        self.HOST = HOST
        self.SERIAL = SERIAL
        self.BEACON = BEACON
        self.BCNTXT = BCNTXT
        self.LON = LON
        self.LAT = LAT
        self.ALT = ALT
        self.PASS = PASS
        self.USER = USER
        self.BLN1 = f"{USER} iGate is up - RF-IS 144.39 MHz"  # Bulletin
        self.ser = None
        self.sck = None

        self.pos_f = format_position(self.LON, self.LAT)
        self.pos_c = compress_position(self.LON, self.LAT, self.ALT)

    # Define signal handler for ^C (exit program)
    def signal_handler(self, interupt_signal, frame):
        print("\r\nCtrl+C, exiting.")
        self.ser.close()
        os._exit(0)

    @property
    def aprs_con(self) -> bool:
        """
        Connect to APRS-IS server
        :return: True or False depending on the success.
        """
        l_time = time.strftime("%H:%M:%S")
        if self.sck is None or type(self.sck) is not classmethod:
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
        login = sock_file.readline().strip()  # 1st response line
        print(f"{l_time}  {Color.GREEN}{login}{Color.END}")
        # if second line contains "unverified", login was not successful
        login = sock_file.readline().strip()  # 2nd response line
        print(f"{l_time}  {Color.GREEN}{login}{Color.END}")
        if login.find("# logresp") >= 0 and login.find(" verified") > 0:
            return True
        elif login.find("# ") >= 0 and login.find("unverified") == -1:
            print(
                f"{l_time} {Color.YELLOW}Something during login went wrong.{Color.END}"
            )
            return True
        else:
            print(
                f"{l_time} {Color.RED}Login not successful. Check call sign and verification code.{Color.END}"
            )
            exit(0)

    # todo Add Logging
    def send_aprs(self, aprs_string: str) -> bool:
        """
        Send aprs data to APRS-IS, used for beacon and bulletin
        :param aprs_string:
        :return: Boolean indicating Success or failure
        """
        l_time = time.strftime("%H:%M:%S")
        try:
            if is_internet():
                self.sck.sendall(bytes(aprs_string, "ascii"))
                print(f"{l_time} {Color.BLUE}{aprs_string.strip()}{Color.END}")
                return True
            else:
                err = "No internet"
        except TimeoutError as msg:
            err = msg.strerror
        except BrokenPipeError as msg:
            err = msg.strerror
        except OSError as msg:
            err = msg.strerror
        if len(err) > 0:
            print(
                f"{l_time} {Color.YELLOW}{err} Trying to re-establish connection ...{Color.END}"
            )
            time.sleep(2.0)
            if self.aprs_con:
                self.sck.sendall(bytes(aprs_string, "ascii"))
                print(f"{l_time} {Color.BLUE}{aprs_string.strip()}{Color.END}")
                return True
            else:
                print(
                    f"{l_time} {Color.RED}Not sent: {Color.YELLOW}{aprs_string.strip()}{Color.END}"
                )
                return False

    def send_my_position(self):
        """
        thread that sends position every BEACON sec to APRS IS
        """
        position_string = f"{self.USER}>APRS,TCPIP*:={self.pos_c}{self.BCNTXT}\n"
        threading.Timer(self.BEACON, self.send_my_position).start()
        self.send_aprs(position_string)

    def send_bulletin(self):
        """
        thread that sends bulletin every HOURLY sec to APRS IS
        """
        bulletin = f"{self.USER}>APRS,TCPIP*::BLN1     :{self.BLN1}\n"
        threading.Timer(self.HOURLY, self.send_bulletin).start()
        self.send_aprs(bulletin)

    def open_serial(self):
        """
        Opens serial port with 9600 Bd
        :return: exit program when serial could not be opened
        """
        try:
            # open first usb serial port
            self.ser = serial.Serial(self.SERIAL, 9600)
            return
        except Exception as err:
            print(
                " " * 9
                + f"{Color.RED}Serial interface cannot be initialized{Color.END}"
            )
            print(" " * 9 + f"{Color.RED}Check connection and driver name{Color.END}")
            print(" " * 9 + f"{Color.RED}Error {str(err)}{Color.END}")
            exit(0)

    def start(self):
        """
        Starts Igate and runs in loop until terminated with Ctrl C
        :return: nil
        """
        signal.signal(signal.SIGINT, self.signal_handler)
        loc_time = time.strftime("%H:%M:%S")
        loc_date = time.strftime("%y-%m-%d")
        print(
            f"{Color.GREEN}{loc_date} {self.USER} IGgate started - Program by 9V1KG{Color.END}"
        )
        print(" " * 9 + f"Position: {self.pos_f}")

        self.open_serial()
        if is_internet():  # check internet connection
            print(f"{loc_time} Logging in to {self.HOST}")
            if self.aprs_con:
                self.send_my_position()
                self.send_bulletin()
            else:
                print(
                    f"{loc_time} {Color.RED}Cannot establish connection to APRS server{Color.END}"
                )
                self.ser.close()
                exit(0)
        else:
            print(f"{loc_time} {Color.RED}No internet available{Color.END}")
            self.ser.close()
            exit(0)

        while True:
            b_read = self.ser.read_until()
            try:
                line = b_read.decode("ascii").strip("\n\r")
                # print(f'{Color.PURPLE}{line}{Color.END}')  # debug only
                if re.search(" \[.*\] <UI.*>:", line):  # contains " [date time] <UI *>"
                    localtime = time.strftime("%H:%M:%S")
                    routing = line
                    routing = re.sub(
                        " \[.*\] <UI.*>:", f",qAR,{self.USER}:", routing
                    )  # replace "[...]<...>" with ",qAR,Call:"
                    b_read = self.ser.read_until()  # payload
                    try:
                        payload = b_read.decode("ascii").strip("\n\r")
                        packet = bytes(
                            routing + payload + "\r\n", "ascii"
                        )  # byte string
                        # print(f'{Color.PURPLE}{packet}{Color.END}')  # debug only
                    except UnicodeDecodeError as msg:
                        print(
                            f"{localtime} {Color.YELLOW}DecodeError: at pos {msg.start}: "
                            + f"{b_read[msg.start:msg.end]}{Color.END}"
                        )
                        print(f"         {b_read}")
                        packet = bytes(routing, "ascii") + b_read  # byte string
                        payload = " "

                    if len(payload) == 0:
                        message = "No Payload, not gated"
                    elif re.search(
                        r",TCP", routing
                    ):  # drop packets sourced from internet
                        message = "Internet packet not gated"
                    elif re.search(
                        r"^}.*,TCP.*:", payload
                    ):  # drop packets sourced from internet in third party packets
                        message = "Internet packet not gated"
                    elif "RFONLY" in routing:
                        message = "RFONLY, not gated"
                    elif "NOGATE" in routing:
                        message = "NOGATE, not gated"
                    else:
                        message = f"{packet}"[2:-5]  # no b' and \r\n
                        # print(f'{Color.PURPLE}{message}{Color.END}')  # debug only
                        err = ""
                        try:
                            self.sck.sendall(packet)
                            print(f"{localtime} {message}")
                            message = ""
                        except TimeoutError:
                            err = "Timeout"
                        except BrokenPipeError:
                            err = "BrokenPipe"
                        except OSError:
                            err = "OSError"
                        if len(err) > 0:  # try to reconnect
                            if self.aprs_con:
                                self.sck.sendall(packet)
                                print(f"{localtime} {message}")
                                message = ""
                            else:
                                message = f"No network/internet: {err}, not gated"
                        if len(message) > 0:
                            print(
                                f"{localtime} {Color.YELLOW}{message}: "
                                + f"{packet}"[2:-5]
                                + Color.END
                            )
            except UnicodeDecodeError as msg:
                localtime = time.strftime("%H:%M:%S")
                print(
                    f"{localtime} {Color.YELLOW}Packet with DecodeError: at pos {msg.start}: "
                    + f"{b_read[msg.start:msg.end]}{Color.END}:"
                )
                print(" " * 9 + f"{b_read}")


if __name__ == "__main__":
    igate = Ygate()
    igate.start()
