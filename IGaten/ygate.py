"""
    Ygate-n Yaesu igate
    This script is based on an idea from Craig Lamparter
    https://github.com/hessu/ygate

    9V1KG Klaus D Goepel -
    https://klsin.bpmsg.com
    https://github.com/9V1KG/Igate-n

    DU3TW (M0FGC)
    Slight mods

    Version 2020-04-19
"""
#  todo: line wrap in print statements

import sys
import os
import re
import signal
import socket
import threading
import datetime
import time
import math
import textwrap
import serial
import requests


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


WRAP = 120

# data types for received payload
APRS_DATA_TYPE = {
    ":": "MSG ",  # Message or bulletin
    ";": "OBJ ",  # Object
    "=": "POS ",  # Position without timestamp (with APRS messaging)
    "!": "POS ",  # Position without timestamp (no APRS messaging), or Ultimeter 2000 WX Station
    "/": "POS ",  # Position with timestamp (no APRS messaging)
    "@": "POS ",  # Position with timestamp (with APRS messaging)
    "$": "NMEA",  # Raw GPS data or Ultimeter 2000
    ")": "ITEM",  # Item
    "}": "3PRT",  # Third-party traffic
    "`": "MICE",  # Current Mic-E Data (not used in TM-D700)
    "'": "MICE",  # Old Mic-E Data (but Current data for TM-D700)
    "?": "QURY",  # Query
    ">": "STAT",  # Status
    "<": "CAP ",  # Station Capabilities
    "T": "TEL ",  # Telemetry data
    "#": "WX  ",  # Peet Bros U-II Weather Station
    "*": "WX  ",  # Peet Bros U-II Weather Station
    ",": "TEST",  # Invalid data or test data
    "_": "WX  ",  # Weather Report (without position)
    "{": "USER"   # User-Defined APRS packet format
}

# Message types for MIC-E encoded frames
MSG_TYP = {"std": 0, "cst": 1}
MSG_ID = {
    0: ["Emergency", "Emergency,"],
    1: ["Priority", "Custom-6"],
    2: ["Special", "Custom-5"],
    3: ["Committed", "Custom-4"],
    4: ["Returning", "Custom-3"],
    5: ["In Service", "Custom-2"],
    6: ["En Route", "Custom-1"],
    7: ["Off Duty", "Custom-0"],
}


def format_position(lat: tuple, lon: tuple) -> str:
    """
    # Formatted uncompressed APRS Position String
    :param lon: Tuple of Degree, Decimal-Minutes, "N or S"
    :param lat: Tuple of Degree, Decimal-Minutes , "E or W"
    :return: Aprs formatted string
    """
    symbol = "/#"  # Gateway symbol
    lat = "{:02d}".format(lat[0]) + "{:05.2f}".format(lat[1]) + lat[2]
    lon = "{:03d}".format(lon[0]) + "{:05.2f}".format(lon[1]) + lon[2]
    return f"{lat}{symbol[0]}{lon}{symbol[1]}"


def b91_encode(v_int: int) -> str:
    """
    Calculates an ASCII string base 91 from r
    Max: 91 ** 4 = 68 574 961
    :param v_int: scaled position latitude or longitude
    :return: character string
    """
    l_str = ""
    for i in range(0, 5):
        dvr = 91 ** (4 - i)
        l_str += chr(int(v_int / dvr) + 33)
        v_int = v_int % dvr
    return l_str.lstrip("!")


def b91_decode(l_str: str) -> int:
    """
    Decodes ASCII string base 91 to number
    :param l_str: base 91 encoded ASCII string
    :return: r result
    """
    l_len = len(l_str) - 1
    v_int = 0
    for i, l_chr in enumerate(l_str):
        v_int += (ord(l_chr)-33) * 91**(l_len-i)
    return v_int


def compress_position(lat: tuple, lon: tuple, alt: tuple = (0.0, "m")) -> str:
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
    v_int = int(380926 * (90.0 - lat_dec))
    lstr += b91_encode(v_int)  # Compressed Latitude XXXX
    v_int = int(190463 * (180.0 + lon_dec))
    lstr += b91_encode(v_int)  # Compressed Longitude YYYY

    lstr += symbol[1]  # station symbol

    if alt[0] == 0.:
        lstr += "   "  # no altitude data
    else:  # csT bytes
        h_ft = alt[0]/0.3048 if "m" in alt[1] else alt[0]
        a_pot = int(math.log(h_ft) / math.log(1.002))
        lstr += chr(33 + int(a_pot / 91)) + chr(33 + int(a_pot % 91))
        lstr += chr(33 + int("00110010", 2) + 33)  # comp type altitude
    return lstr


def decode_ascii(b_str) -> tuple:
    """
    Decodes byte string highlighting decode errors
    :param b_str: Byte string to be decoded
    :return: number of invalid bytes, string with non ascii bytes highlighted
    """
    inv_byt = 0  # number of invalid bytes
    str_dec = ""
    while len(b_str) > 0:
        try:
            str_dec += b_str.decode("ascii").strip("\r\n")
            b_str = b""
        except UnicodeDecodeError as msg:
            inv_byt += 1
            str_dec += (f"{b_str[:msg.start]}"[2:-1]) \
                + Color.RED \
                + (f"{b_str[msg.start:msg.end]}"[2:-1]) \
                + Color.END
            b_str = b_str[msg.end:]
    return inv_byt, str_dec


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
    except requests.HTTPError as h_err:
        print(
            f"{Color.RED}Internet connection failed, "
            f"status code {h_err.response.status_code}{Color.END}"
        )
        return False
    except requests.ConnectionError:
        return False


def cnv_ch(o_chr: chr) -> chr:
    """
    Character decoding for MIC-E destination field
    used in mic_e_decoding
    :param o_chr: original char
    :return: modified char
    """
    if o_chr in ["K", "L", "Z"]:  # ambiguity
        return chr(48)
    if ord(o_chr) > 79:
        return chr(ord(o_chr) - 32)
    if ord(o_chr) > 64:
        return chr(ord(o_chr) - 17)
    return o_chr


def mic_e_decode(route: str, m_i: bytes) -> str:
    """
    Decodes APRS MIC-E encoded data
    :param route: routing field
    :param m_i: payload bytes
    :return: str with decoded information
    """
    # Check input validity
    m_d = re.search(r">([A-Z,\d]{6,7}),", route)  # extract destination
    if not m_d:
        return "Invalid destination field"
    m_d = m_d.group(1)
    # Check validity of input parameters
    if not re.search(r"[0-9A-Z]{3}[0-9L-Z]{3,4}$", m_d):
        return "Invalid destination field"
    if not re.match(
            r"[\x1c\x1d`'][&-~,\x7f][&-a][\x1c-~,\x7f]{5,}", m_i.decode("ascii")
    ):
        return "Invalid information field"

    # Message type first three bytes destination field
    msg_t: str = "std"
    mbits: int = 0  # message bits (0 - 7)
    for i in range(0, 3):
        mbits += (4 >> i) if re.match(r"[A-K,P-Z]", m_d[i]) else 0
    # print("Message bits: {:03b}".format(mbits))
    if re.search(r"[A-K]", m_d[0:3]):
        msg_t = "cst"  # custom
    msg = MSG_ID[mbits][MSG_TYP[msg_t]]

    # Lat N/S, Lon E/W and Lon Offset byte 1 to 6
    lat_d = "S" if re.search(r"[0-L]", m_d[3]) else "N"
    lon_o = 0 if re.search(r"[0-L]", m_d[4]) else 100
    lon_d = "E" if re.search(r"[0-L]", m_d[5]) else "W"
    ambiguity = (len(re.findall(r"[KLZ]", m_d)))
    # Latitude deg and min
    lat = "".join([cnv_ch(ch) for ch in list(m_d)])
    lat_deg = int(lat[0:2])
    lat_min = round(int(lat[2:4]) + int(lat[-2:])/100, 2)

    # MIC-E Information field
    # Longitude deg and min byte 2 to 4 info field
    lon_deg = m_i[1] - 28 if lon_o == 0 else m_i[1] + 72
    lon_deg = lon_deg - 80 if 189 >= lon_deg >= 180 else lon_deg
    lon_deg = lon_deg - 190 if 199 >= lon_deg >= 190 else lon_deg
    lon_min = m_i[2] - 88 if m_i[2] - 28 >= 60 else m_i[2] - 28
    lon_min = round(lon_min + (m_i[3] - 28) / 100, 2)

    # Speed and Course bytes 5 to 7 info field
    spd = (m_i[4] - 28)
    spd = (spd - 80) * 10 if spd >= 80 else spd * 10 + int((m_i[5] - 28) / 10)
    spd = spd - 800 if spd >= 800 else spd
    crs = 100 * ((m_i[5] - 28) % 10) + m_i[6] - 28
    crs = crs - 400 if crs >= 400 else crs

    # Symbol bytes 8 to 9 info field
    symb = chr(m_i[7]) + chr(m_i[8])

    # Check for altitude or telemetry
    alt: int = 0
    if len(m_i) > 9:
        info = decode_ascii(m_i[9:])[1]
        # Check for altitude
        m_alt = re.search(r".{3}}", info)
        if m_alt:
            alt = b91_decode(m_alt.group()[:3]) - 10000
        if m_i[9] in [b"'", b"`", b'\x1d']:
            # todo decode telemetry data
            # "'" 5 HEX, "`" 2 HEX "\x1d" 5 binary
            info = "Telemetry data"
        else:
            info = ""
    """
    Values returned in decoded:
        Position:  lat_deg, lat_min, lat_d; 
                   Lon_deg, lon_min, lon_d
        Ambiguity: ambiguity
        Speed:     spd in knots
        Course:    crs in deg
        Altitude:  alt in m
    """
    decoded = f"Pos: {lat_deg} {lat_min}'{lat_d}, " \
              f"{lon_deg} {lon_min}'{lon_d}, " \
              f"{msg}, "

    if ambiguity > 0:
        decoded += f"Ambgty: {ambiguity} digits, "
    if spd > 0:
        decoded += f"Speed: {spd} knots, "
    if crs > 0:
        decoded += f"Course: {crs} deg, "
    if alt > 0:
        decoded += f"Alt: {alt} m, "
    # decoded += f"Status: {info}"
    return decoded


def print_wrap(text: str):
    """
    Prints test wrapped and indented
    :param text: input string
    :return:
    """
    lines = textwrap.wrap(text, WRAP)
    print(lines.pop(0))
    for line in lines:
        print(textwrap.indent(line, 16 * " "))
    return


class Ygate:
    """
    Yaesu IGate class takes packets sent from Yaesu radio via
    serial (data) interface and forwards them to the APRS
    Internet system (APRS-IS)
    """

    RANGE = 150  # Range filter for APRS-IS in km
    SERIAL = "/dev/ttyUSB0"
    BAUD = 9600
    BCNTXT = "IGate RF-IS 144.39 - 73"

    BLNTXT = "IGate is up - RF-IS for FTM-400: https://github.com/9V1KG/Igate-n"
    HOST = "rotate.aprs2.net"
    PORT = 14580
    HOURLY = 3600.0
    BEACON = 1200.0  # beacon every 20 min
    FORMAT = "ascii"  # APRS uses ASCII
    VERS = "APZ090"  # Software experimental vers 0.9.0

    def __init__(
            self,
            user: str = "MYCALL",
            ssid: int = 10,
            secret: int = 00000,
            latitude: tuple = (14, 7.09, "N"),
            longitude: tuple = (120, 58.07, "E"),
            altitude: tuple = (0.0, "m"),
    ):
        """
        :param user:   Your call sign
        :param ssid:   SSID for the gateway (usually 10 for igate)
        :param secret:     Your aprs secret code
        :param latitude:   Latitude
        :param longitude:  Longitude
        :param altitude:   Altitude in ft or m, 0. if no altitude
        """
        self.user = f"{user}-{ssid}"
        self.secret = f"{secret}"  # nur fuer login
        self.pos = (latitude, longitude, altitude)

        self.ser = None
        self.sck = None
        self.sock_file = None

        # Statistics
        self.start_datetime = datetime.datetime.now()
        self.call_signs = []  # List of unique calls heard
        self.p_gated = 0  # number of gated packets
        self.p_not_gated = 0  # number of not gated packets
        self.p_inv_routing = 0  # number of invalid routing

        self.msg = ""  # Status messages

    def signal_handler(self, interupt_signal, frame):
        """
        Exit program with ctrl c and print statistics
        :param interupt_signal:
        :param frame:
        :return:
        """
        print("\r\nCtrl+C, exiting.")
        print(
            "{:d}".format(self.p_gated + self.p_not_gated
                          + self.p_inv_routing)
            + f" packets received, {self.p_gated} Packets gated "
            f"{self.p_not_gated} Packets not gated, "
            f"{self.p_inv_routing} invalid packets."
        )
        print("List of unique call sign heard:")
        print(self.call_signs)
        self.ser.close()
        # os._exit is used to exit the program
        # immediately, because threats are running
        os._exit(0)

    def is_routing(self, p_str: str) -> bool:
        """
        Check whether p_str is a valid routing packet, add unique call signs to list
        :param p_str: String to be checked
        :return: true if valid p_str starts with a valid call sign
        """
        val_call = re.match(r"\d?[A-Z]{1,2}\d{1,4}[A-Z]{1,4}", p_str)
        if val_call:
            if val_call.group() not in self.call_signs:
                # todo to become part of logging
                self.call_signs.append(val_call.group())
            return True
        return False

    @property
    def aprs_con(self) -> bool:
        """
        Connect to APRS-IS server
        :return: True or False depending on the success.
        """
        l_time = time.strftime("%H:%M:%S")
        if self.sck is None or not isinstance(self.sck, classmethod):
            self.sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # open socket
            self.sck.settimeout(None)
        try:
            self.sck.connect((self.HOST, self.PORT))
        except (OSError, TimeoutError) as msg:
            print(
                f"{l_time} {Color.RED}Unable to connect to APRS-IS server.{Color.END} {msg}"
            )
            return False
        self.sck.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sck.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 512)  # buffer size
        self.sock_file = self.sck.makefile(mode="r")
        login = self.sock_file.readline().strip()  # 1st response line
        print(f"{l_time} {Color.GREEN}{login}{Color.END}")
        time.sleep(1.0)
        # Login to APRS Server
        self.sck.sendall(
            bytes(f"user {self.user} pass {self.secret} "
                  f"vers 9V1KG-ygate 0.9 filter m/{self.RANGE}\r\n", "utf-8")
        )
        # if second line contains "unverified", login was not successful
        if self.sock_file:
            login = self.sock_file.readline()  # 2nd response line
        else:
            self.sock_file = self.sck.makefile(mode="r")
            login = self.sock_file.readline()  # 2nd response line
        if login.find("# logresp") >= 0 and login.find(" verified") > 0:
            print(f"{l_time} {Color.GREEN}{login.strip()}{Color.END}")
            return True
        print(
            f"{l_time} {Color.RED}Login not successful. "
            f"Check call sign and verification code.{Color.END}"
        )
        return False

    def send_aprs(self, aprs_string: str) -> bool:
        """
        Send aprs data to APRS-IS, used for beacon and bulletin
        aprs_string must end with '\n'!
        :param aprs_string:
        :return: Boolean indicating Success or failure
        """
        dt_id = "[MSG ]" if re.search(r"::BLN", aprs_string) else "[POS ]"
        l_time = time.strftime("%H:%M:%S")
        if is_internet():
            try:
                self.sck.sendall(bytes(aprs_string, self.FORMAT))
                print_wrap(f"{l_time} {dt_id} {Color.BLUE}{aprs_string.strip()}{Color.END}")
                return True
            except (TimeoutError, BrokenPipeError, OSError) as msg:
                err = msg.strerror
        else:
            err = "No internet"
        print(
            f"{l_time} {Color.YELLOW}{err} Trying to re-establish connection ...{Color.END}"
        )
        time.sleep(2.0)
        if self.aprs_con:
            self.sck.sendall(bytes(aprs_string, self.FORMAT))
            print_wrap(f"{l_time} {dt_id} {Color.BLUE}{aprs_string.strip()}{Color.END}")
            return True
        print_wrap(
            f"{l_time} {Color.YELLOW}Not sent: {Color.END}{aprs_string.strip()}"
        )
        return False

    def send_my_position(self):
        """
        thread that sends position every BEACON sec to APRS IS
        """
        pos_c = compress_position(self.pos[0], self.pos[1], self.pos[2])
        position_string = f"{self.user}>{self.VERS},TCPIP*:={pos_c}{self.BCNTXT}\n"
        threading.Timer(self.BEACON, self.send_my_position).start()
        self.send_aprs(position_string)

    def send_bulletin(self):
        """
        thread that sends a bulletin every HOURLY sec to APRS IS
        """
        if self.p_gated > 0:
            # send statistics via bulletin
            time_on = datetime.datetime.now() - self.start_datetime
            p_tot = self.p_gated + self.p_not_gated + self.p_inv_routing
            n_calls = len(self.call_signs)
            bulletin_txt = f"IGate up {time_on.days} days " \
                f" {round(time_on.seconds/3600,1)} h - " \
                f"{p_tot} rcvd, {self.p_gated} gtd, " \
                f"{n_calls} unique calls"
        else:
            bulletin_txt = self.BLNTXT
        bulletin = f"{self.user}>{self.VERS},TCPIP*::BLN1     :{self.user} {bulletin_txt}\n"
        threading.Timer(self.HOURLY, self.send_bulletin).start()
        self.send_aprs(bulletin)

    def aprsis_rx(self):
        """
        Receives and prints packets from APRS server
        (command line option -i)
        :return:
        """
        try:  # receive from APRS-IS test function
            rcvd = self.sock_file.readline().strip()
            if len(rcvd) > 0 and rcvd.find("# aprs") == -1:
                print(" " * 9 + f"[IS  ] {rcvd}")
            time.sleep(0.2)
        except UnicodeDecodeError:
            pass

    def check_routing(self, route: str, payld: str) -> bool:
        """
        Check whether the packet should be routed to the internet
        :param route: routing
        :param payld: payload
        :return: true if ok for routing false otherwise
        """
        if len(route) == 0:
            self.msg = "No Payload, not gated"
        elif re.search(r",TCP", route):
            # drop packets sourced from internet
            self.msg = "TCP not gated"
        elif re.search(r"^}.*,TCP.*:", payld):
            # drop packets sourced from internet in third party packets
            self.msg = "TCP not gated"
        elif re.match(r"\?", payld):
            # drop aprs queries
            self.msg = "Query, not gated"
        elif "RFONLY" in route:
            self.msg = "RFONLY, not gated"
        elif "NOGATE" in route:
            self.msg = "NOGATE, not gated"
        else:
            return True
        self.p_not_gated += 1
        return False

    def do_gating(self, packet: bytes) -> bool:
        """
        gate packet to aprs server
        :param packet: the bytes to be sent
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
            self.msg = "No network/internet, not gated"
            self.p_not_gated += 1
            return False

    def open_serial(self) -> bool:
        """
        Opens serial port with self.BAUD Bd
        :param serial_dev: driver string
        :return: True when serial could be opened
        """
        try:
            # open first usb serial port
            self.ser = serial.Serial(self.SERIAL, self.BAUD)
            print(" " * 9 + f"Serial port {self.ser.name} opened")
            return True
        except Exception as err:
            print(
                " " * 9
                + f"{Color.RED}Serial interface cannot be initialized{Color.END}"
            )
            print(" " * 9 + f"{Color.RED}Check connection and driver name{Color.END}")
            print(" " * 9 + f"{Color.RED}Error {str(err)}{Color.END}")
            return False

    def query_reply(self, call: str, p_ld: str):
        """
        Sends reply to a query via APRS-IS
        :param call: Destination call sign
        :param p_ld: original payload
        :return:
        """
        if re.search(r":\?IGATE\?", p_ld):  # Igate
            self.send_aprs(
                f"{self.user}>{self.VERS},TCPIP*::{call.ljust(9)}:"
                f"<IGATE MSG_CNT={self.p_gated} LOC_CNT={len(self.call_signs)}\r\n>"
            )
        if re.search(r":\?APRSD", p_ld):  # Direct heard calls
            self.send_aprs(
                f"{self.user}>{self.VERS},TCPIP*::{call.ljust(9)}:"
                f"Directs= {' '.join(self.call_signs)}\r\n"
            )
        if re.search(r":\?APRSP", p_ld):  # Position
            pos_c = compress_position(self.pos[0], self.pos[1], self.pos[2])
            self.send_aprs(
                f"{self.user}>{self.VERS},TCPIP*::{call.ljust(9)}:"
                f"={pos_c}{self.BCNTXT}\r\n>"
            )
        if re.search(r":\?APRSS", p_ld):  # Status
            self.send_aprs(
                f"{self.user}>{self.VERS},TCPIP*::{call.ljust(9)}:"
                f"{self.BLNTXT}\r\n"
            )

    def get_data_type(self, routing: str, pay_ld: str) -> str:
        """
        Checks for data id and messages to own call sign
        :param routing: valid routing
        :param pay_ld: payload
        :return: message id
        """
        try:
            d_type = APRS_DATA_TYPE[pay_ld[0]]
        except KeyError:
            return "    "
        my_c = re.search(  # get target call for messages
            r":\d?[A-Z]{1,2}\d{1,4}[A-Z]{1,4}-?\d{0,2} {0,6}:",
            pay_ld)
        if my_c and d_type in ["MSG ", "3PRT"]:
            # Check for own messages - remove ssid
            call = re.search(r"\d?[A-Z]{1,2}\d{1,4}[A-Z]{1,4}", my_c.group())
            if call and call.group() == re.split("-", self.user)[0]:
                d_type = f"{Color.PURPLE}MSG!{Color.END}"
                cs_to = re.match(
                    r"\d?[A-Z]{1,2}\d{1,4}[A-Z]{1,4}-?\d{0,2} {0,6}",
                    routing).group()
                # send reply to a query
                self.query_reply(cs_to, pay_ld)
        return d_type

    # todo: move param from __init___ here
    def start_up(self,):
        """
        Startup of IGate: opens serial port and internet connection
        Login to APRS server and send bulletin and beacon
        :return: None
        """
        print(
            f"{Color.GREEN}{(str(self.start_datetime).split('.'))[0]} {self.user} "
            f"IGgate started - Program by 9V1KG{Color.END}"
        )
        print(" " * 9 + f"Formatted  Position: {format_position(self.pos[0], self.pos[1])}")
        print(" " * 9 + f"Compressed Position: {compress_position(self.pos[0], self.pos[1], self.pos[2])}")
        loc_time = time.strftime("%H:%M:%S")
        if not self.open_serial():
            sys.exit(1)
        if is_internet():  # check internet connection
            print(f"{loc_time} Logging in to {self.HOST}")
            if self.aprs_con:
                self.send_bulletin()
                time.sleep(5.)  # wait 5 sec before sending beacon
                self.send_my_position()
            else:
                print(
                    f"{loc_time} {Color.RED}"
                    f"Cannot establish connection to APRS server"
                    f"{Color.END}"
                )
                if self.ser:
                    self.ser.close()
                sys.exit(1)
        else:
            print(f"{loc_time} {Color.RED}No internet available{Color.END}")
            if self.ser:
                self.ser.close()
            sys.exit(1)

    def start(self):
        """
        Runs in a loop until terminated with Ctrl C
        :return: nil
        """
        signal.signal(signal.SIGINT, self.signal_handler)
        self.start_up()

        while True:
            if "-i" in str(sys.argv):  # -i as cmd line argument
                self.aprsis_rx()
            b_read = self.ser.read_until()
            res = decode_ascii(b_read)
            if res[0] > 0:  # invalid ascii char in routing
                localtime = time.strftime("%H:%M:%S")
                print(f"{localtime} {Color.YELLOW}Invalid routing:{Color.END} {res[1]}")
                self.p_inv_routing += 1
            elif self.is_routing(res[1]) and re.search(r" \[.*\] <UI.*>:", res[1]):
                # routing starts with a call sign and contains " [date time] <UI *>"
                localtime = time.strftime("%H:%M:%S")
                routing: str = res[1]
                b_read = self.ser.read_until()  # next line is payload
                res = decode_ascii(b_read)
                payload: str = res[1]  # non ascii chars will be shown as\xnn
                data_type = self.get_data_type(routing, payload)
                if self.check_routing(routing, payload): # can be routed
                    routing = re.sub(
                        r" \[.*\] <UI.*>:", f",qAR,{self.user}:", routing
                    )  # replace "[...]<...>" with ",qAR,Call:"
                    packet = bytes(routing, self.FORMAT) + b_read  # byte string
                    if self.do_gating(packet):
                        print_wrap(f"{localtime} [{data_type}] {routing}{payload}")
                        # Print decoded MIC-E data
                        if data_type == "MICE" and "-d" in str(sys.argv):
                            print(16 * " " + mic_e_decode(routing, b_read))
                    else:
                        routing = re.sub(r" \[.*\] <UI.*>", "", routing)
                        print_wrap(
                            f"{localtime} {Color.YELLOW}{self.msg}{Color.END}: "
                            f"{routing}{payload}"
                        )
                else:
                    routing = re.sub(r" \[.*\] <UI.*>", "", routing)
                    print_wrap(
                        f"{localtime} [{data_type}] {Color.YELLOW}{self.msg}{Color.END}: "
                        f"{routing}{payload}"
                    )
            elif len(res[1]) > 0:
                localtime = time.strftime("%H:%M:%S")
                print_wrap(f"{localtime} {Color.YELLOW}Invalid routing{Color.END} {res[1]}")
                self.p_inv_routing += 1
            else:  # just \r\n disregard
                pass


if __name__ == "__main__":
    YGATE = Ygate()
    YGATE.start()
