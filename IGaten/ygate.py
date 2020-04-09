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
# Version 2020-04-05
#


import os
import re
import signal
import socket
import threading
import datetime
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
    return f"{lat}{symbol[0]}{lon}{symbol[1]}"


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
    lstr = symbol[0]  # symbol table id

    lat_dec = -(lat[0] + lat[1]/60.) if "S" in lat[2] else (lat[0] + lat[1]/60.)
    lon_dec = -(lon[0] + lon[1]/60.) if "W" in lat[2] else (lon[0] + lon[1]/60.)
    r = int(380926 * (90.0 - lat_dec))
    lstr += b91(r)  # Compressed Latitude XXXX
    r = int(190463 * (180.0 + lon_dec))
    lstr += b91(r)  # Compressed Longitude YYYY

    lstr += symbol[1]  # station symbol

    if alt[0] == 0.:
        lstr += "   "  # no altitude data
    else:  # csT bytes
        hf = alt[0]/0.3048 if "m" in alt[1] else alt[0]
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

# classify/decode received payload
aprs_data_type = {
    ":": "MSG ",
    ";": "OBJ ",
    "=": "POS ",
    "!": "POS ",
    "/": "POST",
    "@": "POST",
    "$": "NMEA",
    ")": "ITEM",
    "}": "3PRT",
    "`": "GPS ",
    "'": "GPS ",
    "?": "QURY",
    ">": "STAT",
    "<": "CAP ",
    "T": "TEL ",
    "#": "WX  ",
    "*": "WX  ",
    ",": "TEST",
    "_": "WX  ",
    "{": "USER",
}


class Ygate:

    HOURLY = 3600.0
    FORMAT = "ascii"
    """
    todo: implement message count MSG_CNT and loc count LOC_CNT to 
    respond to an ?IGATE? query. Ensure generic queries data type ?
    not gated!
    """
    MSG_CNT = 0  # messages transmitted
    LOC_CNT = 0  # number of local stns

    def __init__(
        self,
        USER = "MYCALL-10",
        PASS= "0000",
        LAT= (14, 5.09, "N"),
        LON= (119, 58.07, "E"),
        ALT= (0.0, "m"),
        SERIAL= "/dev/ttyUSB0",
        BCNTXT= "IGate RF-IS 144.39 - 73",
        BEACON= 1200.0,
        BLNTXT= "IGate is up - RF-IS for FTM-400: https://github.com/9V1KG/Igate-n",
    ):
        """
        :param USER:   Your callsign with ssid (-10 for igate)
        :param PASS:   Your aprs secret code
        :param LAT:    Latitude
        :param LON:    Longitude
        :param ALT:    Altitude in ft or m, 0. if no altitude
        :param SERIAL: Driver location for serial interface
        :param BCNTXT: Beacon text
        :param BEACON: Beacon frequency in seconds
        :param BLNTXT: Beacon text
        """

        self.user = USER
        self.secret = PASS
        self.lat = LAT
        self.lon = LON
        self.alt = ALT
        self.serial = SERIAL
        self.beacon_txt = BCNTXT
        self.beacon_time = BEACON
        self.bulletin_txt = f"{USER} {BLNTXT}"  # Bulletin

        self.host = "rotate.aprs2.net"
        self.port = 14580
        self.pos_f = format_position(self.lon, self.lat)
        self.pos_c = compress_position(self.lon, self.lat, self.alt)
        self.ser = None
        self.sck = None
        self.sock_file = None

        self.start_datetime = datetime.datetime.now()
        self.call_signs = []  # List of unique calls heard
        self.p_gated = 0  # number of gated packets
        self.p_not_gated = 0  # number of not gated packets
        self.p_inv_routing = 0  # number of invalid routing

        self.msg = ""  # Status message for gating

    # Define signal handler for ^C (exit program)
    def signal_handler(self, interupt_signal, frame):
        print("\r\nCtrl+C, exiting.")
        print(
            "{:d}".format(self.p_gated + self.p_not_gated + self.p_inv_routing) + " packets received, "
            + f"{self.p_gated} Packets gated "
              f"{self.p_not_gated} Packets not gated, "
              f"{self.p_inv_routing} invalid packets."

        )
        print("List of unique call sign heard:")
        print(self.call_signs)
        self.ser.close()
        os._exit(0)

    def is_routing(self, p_str: str) -> bool:
        """
        Check whether p_str is a valid routing packet, add unique call signs to list
        :param p_str: String to be checked
        :return: true if valid
        """
        m = re.search(r"\d?[a-zA-Z]{1,2}\d{1,4}[a-zA-Z]{1,4}", p_str)
        if m and m.pos == 0:
            if m.group() not in self.call_signs:
                # todo to become part of logging
                self.call_signs.append(m.group())
            return True
        else:
            return False

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
            self.sck.connect((self.host, self.port))
        except OSError as msg:
            print(
                f"{l_time} {Color.RED}Unable to connect to APRS-IS server.{Color.END} {msg}"
            )
            return False
        self.sck.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sck.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 512)  # buffer size
        self.sock_file = self.sck.makefile(mode="r")
        login = self.sock_file.readline().strip()  # 1st response line
        print(f"{l_time}  {Color.GREEN}{login}{Color.END}")
        time.sleep(1.0)
        # Login to APRS Server
        # todo: there is still a problem to login to javAPRSSrvr
        self.sck.sendall(
            bytes(f"user {self.user} pass {self.secret} -1 vers ygate-n 0.9 "
                  f"filter m/150\n", self.FORMAT)
        )
        # if second line contains "unverified", login was not successful
        login = self.sock_file.readline().strip()  # 2nd response line
        print(f"{l_time}  {Color.GREEN}{login}{Color.END}")
        if login.find("# logresp") >= 0 and login.find(" verified") > 0:
            return True
        elif (login.find("# aprsc") >= 0 or login.find("# jav") >= 0) \
                and login.find("unverified") == -1:
            # aprs server sends every 20 sec one comment line (#) when logged in
            return True
        else:
            print(
                f"{l_time} {Color.RED}Login not successful. Check call sign and verification code.{Color.END}"
            )
            exit(0)

    def send_aprs(self, aprs_string: str) -> bool:
        """
        Send aprs data to APRS-IS, used for beacon and bulletin
        :param aprs_string:
        :return: Boolean indicating Success or failure
        """
        l_time = time.strftime("%H:%M:%S")
        try:
            if is_internet():
                self.sck.sendall(bytes(aprs_string, self.FORMAT))
                print(f"{l_time} [SELF] {Color.BLUE}{aprs_string.strip()}{Color.END}")
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
                self.sck.sendall(bytes(aprs_string, self.FORMAT))
                print(f"{l_time} [SELF] {Color.BLUE}{aprs_string.strip()}{Color.END}")
                return True
            else:
                print(
                    f"{l_time} {Color.YELLOW}Not sent: {Color.END}{aprs_string.strip()}"
                )
                return False

    def send_my_position(self):
        """
        thread that sends position every BEACON sec to APRS IS
        """
        position_string = f"{self.user}>APRS,TCPIP*:={self.pos_c}{self.beacon_txt}\n"
        threading.Timer(self.beacon_time, self.send_my_position).start()
        self.send_aprs(position_string)

    def send_bulletin(self):
        """
        thread that sends a bulletin every HOURLY sec to APRS IS
        """
        if self.p_gated > 0:
            # send statistics via bulletin
            td = datetime.datetime.now() - self.start_datetime
            p_tot = self.p_gated + self.p_not_gated + self.p_inv_routing
            n_calls = len(self.call_signs)
            self.bulletin_txt = f"IGate up {td.days} days " \
                f" {round(td.seconds/3600,1)} h - " \
                f"{p_tot} rcvd, {self.p_gated} gtd, " \
                f"{n_calls} unique calls"
        bulletin = f"{self.user}>APRS,TCPIP*::BLN1     :{self.bulletin_txt}\n"
        threading.Timer(self.HOURLY, self.send_bulletin).start()
        self.send_aprs(bulletin)

    def aprsis_rx(self):
        try:  # receive from APRS-IS test function
            rcvd = self.sock_file.readline().strip()
            if len(rcvd) > 0 and rcvd.find("# aprs") == -1:
                print(" " * 9 + f"{rcvd}")
            time.sleep(0.2)
        except UnicodeDecodeError:
            pass

    def check_routing(self, p_str: tuple) -> bool:
        """
        Check whether the packet should be routed to the internet
        :param p_str: (routing, payload)
        :return: true if ok for routing
        """
        if len(p_str[0]) == 0:
            self.msg = "No Payload, not gated"
        elif re.search(r",TCP", p_str[0]):
            # drop packets sourced from internet
            self.msg = "TCP not gated"
        elif re.search(r"^}.*,TCP.*:", p_str[1]):
            # drop packets sourced from internet in third party packets
            self.msg = "TCP not gated"
        elif re.match(r"\?", p_str[1]):
            # drop aprs queries
            self.msg = "Query, not gated"
        elif "RFONLY" in p_str[0]:
            self.msg = "RFONLY, not gated"
        elif "NOGATE" in p_str[0]:
            self.msg = "NOGATE, not gated"
        else:
            return True
        self.p_not_gated += 1
        return False

    def do_gating(self, packet: bytes) -> bool:
        """
        gate packet to aprs server
        :param packet:
        :return:
        """
        try:
            self.sck.sendall(packet)
            self.p_gated += 1
            self.msg = ""
            return True
        except (TimeoutError, BrokenPipeError, OSError):
            if self.aprs_con:
                self.sck.sendall(packet)
                self.p_gated += 1
                self.msg = ""
                return True
            else:
                self.msg = "No network/internet, not gated"
                self.p_not_gated += 1
                return False

    def open_serial(self):
        """
        Opens serial port with 9600 Bd
        :return: exit program when serial could not be opened
        """
        try:
            # open first usb serial port
            self.ser = serial.Serial(self.serial, 9600)
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
        print(
            f"{Color.GREEN}{(str(self.start_datetime).split('.'))[0]} {self.user} "
            f"IGgate started - Program by 9V1KG{Color.END}"
        )
        print(" " * 9 + f"Position: {self.pos_f}")
        loc_time = time.strftime("%H:%M:%S")
        self.open_serial()
        if is_internet():  # check internet connection
            print(f"{loc_time} Logging in to {self.host}")
            if self.aprs_con:
                self.send_bulletin()
                time.sleep(5.)  # wait 5 sec before sending beacon
                self.send_my_position()
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
            # self.aprsis_rx()  # test only
            b_read = self.ser.read_until()
            res = decode_ascii(b_read)
            if res[0] > 0:  # invalid ascii char in routing
                localtime = time.strftime("%H:%M:%S")
                print(f"{localtime} {Color.YELLOW}Invalid routing:{Color.END} {res[1]}")
                self.p_inv_routing += 1
            elif self.is_routing(res[1]) and re.search(r" \[.*\] <UI.*>:", res[1]):
                # routing starts with a call sign and contains " [date time] <UI *>"
                localtime = time.strftime("%H:%M:%S")
                routing = res[1]
                b_read = self.ser.read_until()  # next line is payload
                res = decode_ascii(b_read)
                payload = res[1]  # non ascii chars will be passed as they are
                try:
                    data_type = aprs_data_type[payload[0]]
                except KeyError:
                    data_type = "    "
                if self.check_routing((routing, payload)):
                    routing = re.sub(
                        r" \[.*\] <UI.*>:", f",qAR,{self.user}:", routing
                    )  # replace "[...]<...>" with ",qAR,Call:"
                    packet = bytes(routing, self.FORMAT) + b_read  # byte string
                    if self.do_gating(packet):
                        print(
                            f"{localtime} [{data_type}] {routing}{payload}"
                        )
                    else:
                        routing = re.sub(r" \[.*\] <UI.*>", "", routing)
                        print(
                            f"{localtime} {Color.YELLOW}{self.msg}{Color.END}: "
                            f"{routing}{payload}"
                        )
                else:
                    routing = re.sub(r" \[.*\] <UI.*>", "", routing)
                    print(
                        f"{localtime} [{data_type}] {Color.YELLOW}{self.msg}{Color.END}: "
                        f"{routing}{payload}"
                    )
            elif len(res[1]) > 0:
                localtime = time.strftime("%H:%M:%S")
                print(f"{localtime} {Color.YELLOW}Invalid routing{Color.END} {res[1]}")
                self.p_inv_routing += 1
            else:  # just \n\r disregard
                pass


if __name__ == "__main__":
    igate = Ygate()
    igate.start()
