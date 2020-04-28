"""
    Ygate-n Yaesu igate
    This script is based on an idea from Craig Lamparter
    https://github.com/hessu/ygate

    9V1KG Klaus D Goepel -
    https://klsin.bpmsg.com
    https://github.com/9V1KG/Igate-n

    DU3TW (M0FGC)
    Slight mods

    Version 2020-04-27
"""

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
import logging
from collections import namedtuple
import serial
import requests

Col = namedtuple(
    'color',
    ['red', 'green', 'yellow', 'blue', 'purple', 'cyan', 'bold', 'end']
)
COL = Col(red="\033[1;31;48m",
          green="\033[1;32;48m",
          yellow="\033[1;33;48m",
          blue="\033[1;34;48m",
          purple="\033[1;35;48m",
          cyan="\033[1;36;48m",
          bold="\033[1;37;48m",
          end="\033[1;37;0m"
          )

WRAP = 120  # line wrap for terminal output

APRS_DATA_TYPE = {  # data types for received payload
    "!": "POS ",  # 21 Position without timestamp (no APRS messaging), or Ultimeter 2000 WX Station
    "=": "POS ",  # 3D Position without timestamp (with APRS messaging)
    "@": "POS ",  # 40 Position with timestamp (with APRS messaging)
    "/": "POS ",  # 2F Position with timestamp (no APRS messaging)
    "`": "MICE",  # 60 Current Mic-E Data (not used in TM-D700)
    "'": "MICE",  # 27 Old Mic-E Data (but Current data for TM-D700)
    ":": "MSG ",  # 3A Message or bulletin
    "}": "3PRT",  # 7D Third-party traffic
    "T": "TEL ",  # 54 Telemetry data
    "#": "WX  ",  # 23 Peet Bros U-II Weather Station
    "*": "WX  ",  # 2A Peet Bros U-II Weather Station
    "_": "WX  ",  # 5F Weather Report (without position)
    "$": "NMEA",  # 24 Raw GPS data or Ultimeter 2000
    ";": "OBJ ",  # 22 Object
    ")": "ITEM",  # 29 Item
    "?": "QURY",  # 3F Query
    "<": "CAP ",  # 3C Station Capabilities
    ">": "STAT",  # 3E Status
    ",": "TEST",  # 2C Invalid data or test data
    "{": "USER"   # 7B User-Defined APRS packet format
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
    f_pos = f"{lat}{symbol[0]}{lon}{symbol[1]}"
    if re.match(  # check validity of position
            r"[0-8]\d[0-5]\d\.\d\d[N,S][/,\\][0,1][0-7]\d[0-5]\d\.\d{2}[E,W].",
            f_pos
    ):
        return f_pos
    return f"{COL.red}Invalid position input{COL.end}"


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
                       + COL.red \
                       + (f"{b_str[msg.start:msg.end]}"[2:-1]) \
                       + COL.end
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
            f"{COL.red}Internet connection failed, "
            f"status code {h_err.response.status_code}{COL.end}"
        )
        return False
    except requests.ConnectionError:
        logging.warning("request.ConnectionError")
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
    :return: str with decoded information or empty
    """
    # Check input
    if chr(m_i[0]) not in ["'", "`"]:
        return ""
    m_d = re.search(r">([A-Z,\d]{6,7}),", route)  # extract destination
    if not m_d:
        return ""
    m_d = m_d.group(1)
    # Check validity of input parameters
    if not re.search(r"[0-9A-Z]{3}[0-9L-Z]{3,4}$", m_d):
        return "Invalid destination field"
    if not re.match(
            r"[\x1c\x1d`'][&-~,\x7f][&-a][\x1c-~,\x7f]{5,}", m_i.decode("ascii")
    ):
        return ""

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
    # symb = chr(m_i[7]) + chr(m_i[8])

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
            # info = "Telemetry data"
            pass
        """
        Values returned in decoded:
        Position:  lat_deg, lat_min, lat_d; 
                   lon_deg, lon_min, lon_d
        Message:   msg
        If not equal zero:
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


class Ygate:
    """
    Yaesu IGate class takes packets sent from Yaesu radio via
    serial (data) interface and forwards them to the APRS
    Internet system (APRS-IS)
    """
    RANGE = 150  # Range filter for APRS-IS in km
    SERIAL = "/dev/ttyUSB0"
    BAUD = 9600
    BCNTXT = "IGate RF-IS 144.1 - 73"
    STATUS_TXT = "IGate is up - RF-IS for FTM-400: https://github.com/9V1KG/Igate-n"
    HOST = "rotate.aprs2.net"
    PORT = 14580
    HOURLY = 3600.0
    BEACON = 1200.0  # beacon every 20 min
    FORMAT = "ascii"  # APRS uses ASCII
    VERS = "APZ028"  # Software experimental vers 0.28.0
    SPECIAL_CALLS = ["USNAP1", "PSAT", "PCSAT", "AISAT"]
    LOG_FILE = "ygate.log"

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
        User = namedtuple("User", ["my_call", "ssid", "secret", "pos"])

        self.user = User(  # user
            my_call=user,
            ssid=ssid,
            secret=secret,
            pos=(latitude, longitude, altitude)
        )

        self.pstat = [0, 0, 0, []]

        logging.basicConfig(  # logging
            filename=self.LOG_FILE,
            level=logging.INFO,
            format='%(asctime)s %(message)s'
        )

        self.start_datetime = datetime.datetime.now()
        self.msg = ""  # Status messages
        self.ser = None
        self.sck = None
        self.sock_file = None


    def signal_handler(self, interupt_signal, frame):
        """
        Exit program with ctrl c and print statistics
        :param interupt_signal:
        :param frame:
        :return:
        """
        print("\r\nCtrl+C, exiting.")
        print(
            "{:d}".format(self.pstat[0] + self.pstat[1]
                          + self.pstat[2])
            + f" packets received, {self.pstat[0]} Packets gated "
            f"{self.pstat[1]} Packets not gated, "
            f"{self.pstat[2]} invalid packets."
        )
        print("List of unique call sign heard:")
        print(self.pstat[3])
        self.ser.close()
        logging.info(self.pstat)
        logging.info("Program exit\r\n")
        # os._exit is used to exit the program
        # immediately, because threats are running
        os._exit(0)

    def is_routing(self, p_str: str) -> bool:
        """
        Check whether p_str is a valid routing packet, add unique call signs to list
        :param p_str: String to be checked
        :return: true if valid p_str starts with a valid call sign
        """
        # check for normal calls
        val_call = re.match(r"\d?[A-Z]{1,2}\d{1,4}[A-Z]{1,4}", p_str)
        if val_call:
            if val_call.group() not in self.pstat[3]:
                self.pstat[3].append(val_call.group())
            return True
        # check for possible aliases/special calls
        val_call = re.match(r"([A-Z\d]{4,7})(-\d{1,2})?", p_str)
        if val_call and val_call.group(1) in self.SPECIAL_CALLS:
            if val_call.group() not in self.pstat[3]:
                self.pstat[3].append(val_call.group())
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
                f"{l_time} {COL.red}Unable to connect to APRS-IS server.{COL.end} {msg}"
            )
            return False
        self.sck.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sck.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 512)  # buffer size
        self.sock_file = self.sck.makefile(mode="r")
        login = self.sock_file.readline().strip()  # 1st response line
        print(f"{l_time} {COL.green}{login}{COL.end}")
        time.sleep(1.0)
        # Login to APRS Server
        self.sck.sendall(
            bytes(f"user {self.user.my_call}-{self.user.ssid} pass {self.user.secret} "
                  f"vers 9V1KG-ygate 0.9 filter m/{self.RANGE}\r\n", "utf-8")
        )
        # if second line contains "unverified", login was not successful
        if self.sock_file:
            login = self.sock_file.readline()  # 2nd response line
        else:
            self.sock_file = self.sck.makefile(mode="r")
            login = self.sock_file.readline()  # 2nd response line
        if login.find("# logresp") >= 0 and login.find(" verified") > 0:
            print(f"{l_time} {COL.green}{login.strip()}{COL.end}")
            logging.info("%s", login.strip())
            return True
        print(
            f"{l_time} {COL.red}Login not successful. "
            f"Check call sign and verification code.{COL.end}"
        )
        return False

    def send_aprs(self, aprs_string: str) -> bool:
        """
        Send aprs data to APRS-IS, used for beacon and bulletin
        aprs_string must end with '\n'!
        :param aprs_string:
        :return: Boolean indicating Success or failure
        """
        dt_id = APRS_DATA_TYPE[aprs_string.split(":")[1][0]]
        l_time = time.strftime("%H:%M:%S")
        if is_internet():
            try:
                self.sck.sendall(bytes(aprs_string, self.FORMAT))
                logging.debug("[%s] %s", dt_id, aprs_string.strip())
                print_wrap(f"{l_time} [{dt_id}] {COL.blue}{aprs_string.strip()}{COL.end}")
                return True
            except (TimeoutError, BrokenPipeError, OSError) as msg:
                err = msg.strerror
        else:
            err = "No internet"
        logging.debug(err)
        print_wrap(
            f"{l_time} {COL.yellow}{err} Trying to re-establish connection ...{COL.end}"
        )
        time.sleep(2.0)
        if self.aprs_con:
            self.sck.sendall(bytes(aprs_string, self.FORMAT))
            logging.debug("[%s] %s", dt_id, aprs_string.strip())
            print_wrap(f"{l_time} [{dt_id}] {COL.blue}{aprs_string.strip()}{COL.end}")
            return True
        logging.warning("[    ] Not sent: %s", aprs_string.strip())
        print_wrap(
            f"{l_time} {COL.yellow}Not sent: {COL.end}{aprs_string.strip()}"
        )
        return False

    def send_my_position(self):
        """
        thread that sends position every BEACON sec to APRS IS
        """
        pos_c = compress_position(self.user.pos[0], self.user.pos[1], self.user.pos[2])
        position_string = f"{self.user.my_call}-{self.user.ssid}" \
                          f">{self.VERS},TCPIP*:={pos_c}{self.BCNTXT}\n"
        threading.Timer(self.BEACON, self.send_my_position).start()
        self.send_aprs(position_string)

    def send_status(self):
        """
        thread that sends a bulletin every HOURLY sec to APRS IS
        """
        if self.pstat[0] > 0:
            # send statistics via bulletin
            time_on = datetime.datetime.now() - self.start_datetime
            p_tot = self.pstat[0] + self.pstat[1] + self.pstat[2]
            n_calls = len(self.pstat[3])
            status_txt = f"IGate up {time_on.days} days " \
                f"{round(time_on.seconds/3600,1)} h " \
                f"{p_tot} rcvd, {self.pstat[0]} gtd, " \
                f"{n_calls} unique calls"
        else:
            status_txt = self.STATUS_TXT
        status = f"{self.user.my_call}-{self.user.ssid}>{self.VERS}," \
                   f"TCPIP*:>{status_txt}\r\n"
        threading.Timer(self.HOURLY, self.send_status).start()
        self.send_aprs(status)

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
        self.pstat[1] += 1
        return False

    def do_gating(self, packet: bytes) -> bool:
        """
        gate packet to aprs server
        :param packet: the bytes to be sent
        :return:
        """
        try:
            self.sck.sendall(packet)
            self.pstat[0] += 1
            self.msg = ""
            return True
        except (TimeoutError, BrokenPipeError, OSError):
            if self.aprs_con:
                self.sck.sendall(packet)
                self.pstat[0] += 1
                self.msg = ""
                return True
            self.msg = "No network/internet, not gated"
            self.pstat[1] += 1
            return False

    def open_serial(self) -> bool:
        """
        Opens serial port with self.BAUD Bd
        :return: True when serial could be opened
        """
        try:
            # open first usb serial port
            self.ser = serial.Serial(self.SERIAL, self.BAUD)
            print(" " * 9 + f"Serial port {self.ser.name} opened")
            return True
        except (serial.SerialException, serial.SerialTimeoutException) as err:
            print(
                " " * 9
                + f"{COL.red}Serial interface cannot be initialized{COL.end}"
            )
            print(" " * 9 + f"{COL.red}Check connection and driver name{COL.end}")
            print(" " * 9 + f"{COL.red}Error {str(err)}{COL.end}")
            logging.warning("%s", str(err))
            return False

    def query_reply(self, call: str, p_ld: str):
        """
        Sends reply to a query via APRS-IS - \r\n!
        :param call: Destination call sign
        :param p_ld: original payload
        :return:
        """
        dest = f"{self.user.my_call}-{self.user.ssid}>{self.VERS},TCPIP*:"
        if re.search(r":\?IGATE\?", p_ld):  # Igate
            self.send_aprs(
                f"{dest}:{call.ljust(9)}:"
                f"<IGATE,MSG_CNT={self.pstat[0]} LOC_CNT={len(self.pstat[3])}\r\n"
            )
        if re.search(r":\?APRSD", p_ld):  # Direct heard calls
            self.send_aprs(
                f"{dest}:{call.ljust(9)}:"
                f"Directs= {' '.join(self.pstat[3])}\r\n"
            )
        if re.search(r":\?APRSS", p_ld):  # Status
            time_on = datetime.datetime.now() - self.start_datetime
            txt = f"IGate up {time_on.days} days {round(time_on.seconds/3600,1)} h"
            self.send_aprs(
                f"{dest}:{call.ljust(9)}:{txt}\r\n"
            )
        if re.search(r":\?APRSP", p_ld):  # Position
            pos_c = compress_position(self.user.pos[0], self.user.pos[1], self.user.pos[2])
            self.send_aprs(
                f"{dest}={pos_c}{self.BCNTXT}\r\n"
            )

    def get_data_type(self, routing: str, pay_ld: str) -> str:
        """
        Checks for data id and messages to own call sign
        Sends reply to directed queries
        :param routing: valid routing
        :param pay_ld: payload
        :return: message id
        """
        full_call = re.compile(
            r":?((\d?[A-Z]{1,2}\d{1,4}[A-Z]{1,4})-?\d{0,2}) {0,6}[>:]?"
        )  # ":CALL-NN  : or CALL-NN>
        try:
            d_type = APRS_DATA_TYPE[pay_ld[0]]
        except (KeyError, IndexError):
            return "NONE"
        if d_type in ["MSG ", "3PRT"]:  # Check for own messages
            my_c = full_call.search(pay_ld)
            if my_c and my_c.group(2) in self.user:
                d_type = f"{COL.purple}{d_type}{COL.end}"
                cs_to = full_call.match(routing).group(1)
                if cs_to and re.search(r":\?", pay_ld):
                    # send reply to a query to cs_to
                    self.query_reply(cs_to, pay_ld)
            elif re.search(r":BLN", pay_ld):
                d_type = "BLN "
        return d_type

    # todo: move param from __init___ here
    def start_up(self,):
        """
        Startup of IGate: opens serial port and internet connection
        Login to APRS server and send bulletin and beacon
        :return: None
        """
        print(
            f"{COL.green}{(str(self.start_datetime).split('.'))[0]} "
            f"{self.user.my_call}-{self.user.ssid} "
            f"IGgate started - Program by 9V1KG{COL.end}"
        )
        pos_c = compress_position(self.user.pos[0], self.user.pos[1], self.user.pos[2])
        pos_f = format_position(self.user.pos[0], self.user.pos[1])
        print(" " * 9 + f"Formatted  Position: {pos_f}")
        print(" " * 9 + f"Compressed Position: {pos_c}")
        logging.info("Ygate program started, version %s", self.VERS)

        loc_time = time.strftime("%H:%M:%S")
        if not self.open_serial():
            sys.exit(1)
        if is_internet():  # check internet connection
            print(f"{loc_time} Logging in to {self.HOST}")
            if self.aprs_con:
                self.send_status()
                time.sleep(5.)  # wait 5 sec before sending beacon
                self.send_my_position()
            else:
                print(
                    f"{loc_time} {COL.red}"
                    f"Cannot establish connection to APRS server"
                    f"{COL.end}"
                )
                if self.ser:
                    self.ser.close()
                sys.exit(1)
        else:
            print(f"{loc_time} {COL.red}No internet available{COL.end}")
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

            a_p1 = decode_ascii(self.ser.read_until())  # 1st line routing
            b_p2 = self.ser.read_until()  # 2nd line payload bytes
            a_p2 = decode_ascii(b_p2)
            routing = a_p1[1]
            payload = a_p2[1]  # non ascii chars will be shown as\xnn
            logging.debug("[FTM ] %s %s", a_p1[1], a_p2[1])
            data_type = self.get_data_type(routing, payload)
            mic_e = mic_e_decode(routing, b_p2)  # mic-e decoding
            localtime = time.strftime("%H:%M:%S")

            if a_p1[0] > 0:  # invalid ascii char in routing
                print_wrap(
                    f"{localtime} [INV ] {COL.yellow}Invalid routing: {COL.end} {a_p1[1]}"
                )
                logging.warning("[INV ] Invalid routing: %s %s", routing, payload)
                self.pstat[2] += 1
            elif self.is_routing(routing) and re.search(r" \[.*\] <UI.*>:", routing):
                # routing starts with a valid call sign and contains " [date time] <UI *>"
                if self.check_routing(routing, payload):  # can be routed
                    routing = re.sub(
                        r" \[.*\] <UI.*>:", f",qAR,{self.user.my_call}-{self.user.ssid}:", routing
                    )  # replace "[...]<...>" with ",qAR,Call:"
                    packet = bytes(routing, self.FORMAT) + b_p2  # byte string
                    if self.do_gating(packet):
                        print_wrap(f"{localtime} [{data_type}] {routing}{payload}")
                        logging.info("[%s] %s %s", data_type, routing, payload)
                    else:
                        routing = re.sub(r" \[.*\] <UI.*>", "", routing)
                        logging.warning("[%s] %s: %s %s", data_type, self.msg, routing, payload)
                        print_wrap(
                            f"{localtime} [{data_type}] {COL.yellow}{self.msg}{COL.end}: "
                            f"{routing}{payload}"
                        )
                else:  # no routing to internet
                    routing = re.sub(r" \[.*\] <UI.*>", "", routing)
                    logging.info("[%s] %s: %s %s", data_type, self.msg, routing, payload)
                    print_wrap(
                        f"{localtime} [{data_type}] {COL.yellow}{self.msg}{COL.end}: "
                        f"{routing}{payload}"
                    )
                if "-d" in str(sys.argv) and len(mic_e) > 0:
                    print(16 * " " + mic_e)
                    logging.info("       %s", mic_e)
            elif len(routing) > 0:  # no invalid char in routing, but not to be routed
                routing = re.sub(r" \[.*\] <UI.*>", "", routing)
                logging.warning("[%s] Invalid routing: %s %s", data_type, routing, payload)
                print_wrap(
                    f"{localtime} [{data_type}] {COL.yellow}"
                    f"Invalid routing:{COL.end} {routing} {payload}")
                self.pstat[2] += 1
                if "-d" in str(sys.argv) and len(mic_e) > 0:
                    print(16 * " " + mic_e)
                    logging.info("       %s", mic_e)


if __name__ == "__main__":
    YGATE = Ygate()
    YGATE.start()
