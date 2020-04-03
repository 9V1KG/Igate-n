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
# Version 2020-04-03
#


import os
import re
import signal
import socket
import threading
import time
import serial
import requests
import math


def format_position(lon: tuple, lat: tuple) -> str:
    """
    # Formatted uncompressed APRS Position String
    :param lon: Tuple of Degree, Decimal-Minutes, "N or S"
    :param lat: Tuple of Degree, Decimal-Minutes , "E or W"
    :return: Aprs formatted string
    """
    symbol = "/#"  # Gateway symbol
    lon = "{:03d}".format(lon[0]) + "{:05.2f}".format(lon[1]) + lon[2]
    lat = "{:02d}".format(lat[0]) + "{:05.2f}".format(lat[1]) + lat[2]
    pos = f"{lat}{symbol[0]}{lon}{symbol[1]}"
    return pos


def b91(r) -> str:
    """
    # Calculates 4 char ASCII string base 91 from r
    :param r: scaled position latitude or longitude
    :return: 4 char string
    """
    ls = ""
    for i in range(0, 4):
        dv = 91 ** (3 - i)
        ls += chr(int(r / dv) + 33)
        r = r % dv
    return ls


def compress_position(lon: tuple, lat: tuple, alt: tuple = (0.0, "m")) -> str:
    """
    # Calculate compressed position info as string
    # uses b91(r)
    :param lon: Tuple of Degree, Decimal-Minutes , "E or W"
    :param lat: Tuple of Degree, Decimal-Minutes, "N or S"
    :param alt: Tuple of altitude, unit "m' or "ft"
    :return: APRS compressed position string
    """
    symbol = "/#"  # Gateway symbol
    lat_dec = lat[0] + lat[1] / 60.0
    if "S" in lat[2]:
        lat_dec *= -1
    lon_dec = lon[0] + lon[1] / 60.0
    if "W" in lon[2]:
        lon_dec *= -1
    lstr = symbol[0]  # symbol table id

    r = int(380926 * (90.0 - lat_dec))
    lstr += b91(r)  # Compressed Latitude XXXX

    r = int(190463 * (180.0 + lon_dec))
    lstr += b91(r)  # Compressed Longitude YYYY
    lstr += symbol[1]  # station symbol

    hf = alt[0]  # Altitude
    if alt[1] == "m":
        hf /= 0.3048  # calculate feet
    if hf == 0.0:
        lstr += "   "  # no altitude data
    else:  # csT bytes
        a = int(math.log(hf) / math.log(1.002))
        lstr += chr(33 + int(a / 91)) + chr(33 + int(a % 91))
        lstr += chr(33 + int("00110010", 2) + 33)  # comp type altitude
    return lstr


def decode_ascii(bstr) -> tuple:
    """
    Decodes byte string highlighting decode errors
    :param bstr: Byte string to be decoded
    :return: number of invalid bytes, string with non ascii bytes highlighted
    """
    nb = 0  # number of invalid bytes
    pl = ""
    while len(bstr) > 0:
        try:
            pl += bstr.decode("ascii").strip("\n\r")
            bstr = b""
        except UnicodeDecodeError as msg:
            nb += 1
            pl += (f"{bstr[:msg.start]}"[2:-1]) \
                + Color.RED \
                + (f"{bstr[msg.start:msg.end]}"[2:-1]) \
                + Color.END
            bstr = bstr[msg.end:]
    return nb, pl


def is_internet(url: str = "http://www.google.com/", timeout: int = 30) -> bool:
    """
    Is there an internet connection
    :param url: String pointing to a URL
    :param timeout: How long we wait in seconds
    :return: true when internet available
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


class Color:
    """
    Colors used by the ygaten project
    """
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
        USER = "MYCALL-10",
        PASS = "00000",
        LAT = (14, 5.09, "N"),
        LON = (119, 58.07, "E"),
        ALT = (670.0, "m"),
        SERIAL = "/dev/ttyUSB0",
        BCNTXT = "IGate RF-IS 144.39 testing phase - 73",
        BEACON = 900.0,
        HOST= "rotate.aprs2.net",
        PORT= 14580,
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

        self.USER = USER
        self.PASS = PASS
        self.LAT = LAT
        self.LON = LON
        self.ALT = ALT
        self.SERIAL = SERIAL
        self.BCNTXT = BCNTXT
        self.BEACON = BEACON
        self.BLN1 = f"{USER} iGate is up - RF-IS 144.39 MHz"  # Bulletin
        self.HOST = HOST
        self.PORT = PORT

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
        time.sleep(1.0)
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
        elif login.find("# aprsc") >= 0 and login.find("unverified") == -1:
            # aprs server sends every 20 sec one comment line when logged in
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
        except (TimeoutError, BrokenPipeError, OSError) as msg:
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

    def startup(self):
        """
        Check that internet and serial are available, if yes, send beacon & bulletin
        :return:
        """
        loc_date = time.strftime("%y-%m-%d")
        print(
            f"{Color.GREEN}{loc_date} {self.USER} IGgate started - Program by 9V1KG{Color.END}"
        )
        print(" " * 9 + f"Position: {self.pos_f}")
        loc_time = time.strftime("%H:%M:%S")
        self.open_serial()
        if is_internet():  # check internet connection
            print(f"{loc_time} Logging in to {self.HOST}")
            if self.aprs_con:
                self.send_my_position()
                self.send_bulletin()
                return
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

    def start(self):
        """
        Starts Igate and runs in loop until terminated with Ctrl C
        :return: nil
        """
        signal.signal(signal.SIGINT, self.signal_handler)
        self.startup()

        while True:
            b_read = self.ser.read_until()
            res = decode_ascii(b_read)
            # print(f'{Color.PURPLE}{res[1]}{Color.END}')  # debug only
            if res[0] > 0:
                print(" " * 9 + f"{Color.YELLOW}Invalid routing:{Color.END} {res[1]}")
            else:
                if re.search(r" \[.*\] <UI.*>:", res[1]):  # contains " [date time] <UI *>"
                    localtime = time.strftime("%H:%M:%S")
                    routing = res[1]
                    routing = re.sub(
                        r" \[.*\] <UI.*>:", f",qAR,{self.USER}:", routing
                    )  # replace "[...]<...>" with ",qAR,Call:"
                    b_read = self.ser.read_until()  # payload
                    res = decode_ascii(b_read)
                    # print(f'{Color.PURPLE}{res[1]}{Color.END}')  # debug only
                    payload = res[1]
                    packet = bytes(routing, "ascii") + b_read  # byte string
                    if len(payload) == 0:
                        message = "No Payload, not gated"
                    elif re.search(r",TCP", routing):
                        # drop packets sourced from internet
                        message = "Internet packet not gated"
                    elif re.search(r"^}.*,TCP.*:", payload):
                        # drop packets sourced from internet in third party packets
                        message = "Internet packet not gated"
                    elif "RFONLY" in routing:
                        message = "RFONLY, not gated"
                    elif "NOGATE" in routing:
                        message = "NOGATE, not gated"
                    else:
                        message = f"{packet}"[2:-5]  # no b' and \r\n
                        # print(f'{Color.PURPLE}{message}{Color.END}')  # debug only
                        try:
                            self.sck.sendall(packet)
                            print(f"{localtime} {message}")
                            message = ""
                        except (TimeoutError, BrokenPipeError, OSError):
                            if self.aprs_con:
                                self.sck.sendall(packet)
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


if __name__ == "__main__":
    igate = Ygate()
    igate.start()
