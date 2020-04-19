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
- Command line option -d to show Mic-E decoded Info
- Command line option -i to show frames received from APRS-IS 
- Checks and recovers from lost network/internet connection
- Beacon of your position and altitude in compressed format
- Hourly bulletin showing up-time, received/gated packets and unique calls
- Checks packet payload decoding and highlight invalid bytes
- Displays APRS data type POS, MSG, MICE, WX etc.
- Replies to queries ?APRSP, ?APRSD, ?APRSS, ?IGATE?
- Colored terminal text output

## User Settings
Please modify the following parameter in `ygaten.py` according 
to your requirements:

     Class parameter:
     user:      your call sign, e.g. DU1KG
     ssid:      ssid for the gateway (default 10)
     secret:    your APRS 5-digit pass code
     latitude:  Latitude and 
     longitude: Longitude of your position in the format
                (degrees, minutes as decimal number, N/S/E/W)
     altitude:  Altitude in meter "m" or feet "ft", (0.,"m") if none
     
     CLASS CONSTANTS
     RANGE:  Filter range in km (default 150) 
     SERIAL: Serial driver (default "/dev/ttyUSB0")

## Radio Setup FTM-400
    Setup -> APRS -> (5) APRS Modem -> ON
    Setup -> DATA -> (1) COM PORT SETTINGS
        SPEED     -> 9600 bps
        OUTPUT    -> PACKET
        WP FORMAT -> NMEA 9
    Setup -> DATA -> (3) DATA SPEED
        APRS 1200 bps
        DATA 9600 bps

## Install and Run

For a simple installation as python script, copy the file `ygaten.py` into your directory 
and make it executable.
Modify the parameter as explained above. Import `pySerial` and `requests` with:

    pip install pySerial
    pip install requests

Start the program from the command line window in your directory with: 

    python3 ygaten.py [-d] [-i]

Stop the program with `ctrl c`.

Please see the document [Install And Run](Install_run.md) for alternative installation as a module and more information.
