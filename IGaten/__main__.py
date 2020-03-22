# Main program
from IGaten import Ygate, Color
import serial
import signal
import time

if __name__ == "__main__":
    yg = Ygate()
    yg.start()
