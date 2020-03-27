# Yaesu APRS IGate new

The script is based on the idea from Craig Lamparter 
https://github.com/hessu/ygate
This version is a heavily modified and improved version by 
(c) 9V1KG

The script will turn your Yaesu radio (FT1D, FTM-100, FTM-400) into a receive-only APRS IGate.
All APRS packet traffic received by your radio will be forwarded to the Internet
(APRS-IS Servers) for further routing. Just connect the Yaesu supplied USB cable from
your radio to the computer and run the script under Python 3.

The script is still experimental under testing on MacOS and Raspberry Pi 3B+. It should run 
on Windows too

## Features
- Runs under Python 3 (tested with 3.7 and 3.8)
- When started, checks for serial connection 
- Checks and recovers from lost network/internet connection
- Beacon (and bulletin)
- Checks packet payload decoding
- Colored terminal text output (yellow for warnings, red for errors)

## User Settings
Please modify the following parameter in `ygaten.py` the according to your requirements:

     HOST:   and 
     PORT:   APRS server, usually do not need to be changed.
     USER:   your call sign with ssid, e.g. DU1KG-10
     PASS:   your APRS 5-digit pass code
     LAT:    Latitude and 
     LON:    Longitude of your position in the format
             (degrees, minutes as decimal number, N/S/E/W)
     BCNTXT: Text of the beacon. The beacon will be sent every 
     BEACON: seconds
     SERIAL: The driver for your com port. For MacOS it is 
             "/dev/tty.usbserial-14110", for Linux (Raspberry) 
             "/dev/ttyUSB0". For a Windows PC it will be "COM1:"
             (not tested).

## Install and Run

For a simple installation as python script, copy the file `ygaten.py` into your directory 
and make it executable.
Modify the parameter as explained above. Import `pySerial` and `requests` with:

    pip install pySerial
    pip install requests

Start the program from the command line window in your directory with: 

    python3 ygaten.py

Stop the program with `ctrl c`.

Please see the document [Install And Run](Install_run.md) for alternative installation as a module and more information.
