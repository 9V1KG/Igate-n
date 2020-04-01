import requests
import math
from IGaten import Color


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
