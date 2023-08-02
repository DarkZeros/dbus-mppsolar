#!/usr/bin/env python3

import datetime
import serial

def send_and_receive():
    response_line = None
    try:
        with serial.Serial('/dev/ttyUSB2', 2400, timeout=1, write_timeout=1) as s:
            print(datetime.datetime.now().time(), "Executing command via serialio...")
            s.flushInput()
            s.flushOutput()
            s.write(b'QVFWb\x99\r')
            response_line = s.read_until(b"\r")
            s.read_all()
            print(datetime.datetime.now().time(),"serial response was: %s", response_line)
            #s.close()
        print(datetime.datetime.now().time(), "closed")
        return response_line
    except Exception as e:
        print(f"Serial read error: {e}")

for i in range(10):
    print(datetime.datetime.now().time(), '--------------------')
    send_and_receive()