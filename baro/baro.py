#!/usr/bin/env python3

import serial
from datetime import datetime

ser = serial.Serial("/dev/cu.usbmodem101")

# https://gpsd.gitlab.io/gpsd/NMEA.html#_xdr_transducer_measurement

while True:
    line = ser.readline()

    now = datetime.now()
    line = line.decode().rstrip()
    print(f"{now.isoformat()};{line}")
