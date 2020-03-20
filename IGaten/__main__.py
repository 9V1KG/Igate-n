# Main program
from IGaten import Ygate, Color
import serial
import signal
import time

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    loc_time = time.strftime("%H:%M:%S")
    loc_date = time.strftime("%y-%m-%d")
    print(
        f"{Color.GREEN}{loc_date} {self.USER} IGgate started - Program by 9V1KG{Color.END}"
    )

    POSITION = format_position(self.LON, self.LAT)  # get APRS position string
    print(f"         Position: {POSITION}")

    ser = open_serial()
    sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # open socket
    if is_internet():  # check internet connection
        print(f"{loc_time} Logging in to {HOST}")
        if aprs_con():
            send_my_position()
            # send_bulletin() optional
        else:
            print(f"{loc_time} {Color.YELLOW}No connection to APRS server{Color.END}")
    else:
        print(f"{loc_time} {Color.RED}No internet available{Color.END}")
        ser.close()
        os._exit(0)
