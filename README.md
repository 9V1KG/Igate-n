Ygate-n Yaesu IGate new

This script is based on the idea from Craig Lamparter 
https://github.com/hessu/ygate
This version is a heavily modified and improved version by 
(c) 9V1KG

The script will turn your Yaesu radio (FT1D, FTM-100, FTM-400) into a receive-only APRS IGate.
All APRS packet traffic received by your radio will be forwarded to the Internet
(APRS-IS Servers) for further routing. Just connect the Yaesu supplied USB cable from
your radio to the computer and run the script under Python 3.

The script was tested running on MacOS and Raspberry Pi 3B+

Features:
- Runs under Python 3.7 and 3.8
- When started, checks for serial connection 
- Checks and recovers from lost network/internet connection
- Beacon (and bulletin)
- Checks packet payload decoding
- Colored terminal text output (yellow for warnings, red for errors)

Please modify lines 10 - 19 according to your requirements.

USER: your call sign with ssid, e.g. DU1KG-10
PASS: your APRS 5-digit pass code
LAT and LON: Latitude and Longitude of your position in the format
(degrees, minutes as decimal number, North/South/East/West)

BCNTXT: Text of the beacon. The beacon will be sent ever BEACON seconds

SERIAL: The driver for your com port. For MacOS it is "/dev/tty.usbserial-14110",
for Linux (Raspberry) "/dev/ttyUSB0". For a windows PC it will be "COM1:"
(not tested).

HOST and PORT usually do not need to be changed

Start the program in the command line window with python3 ygate-n.py
Change file permission to allow execute (chmod +x ygate-n.py)
If you get an error message that certain modules are missing
(e.g. pyserial), inport them using "pip install ..."
Stop the program with ctrl c


