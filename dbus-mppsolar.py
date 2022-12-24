#!/usr/bin/env python3

"""
A class to put a simple service on the dbus, according to victron standards, with constantly updating
paths. See example usage below. It is used to generate dummy data for other processes that rely on the
dbus. See files in dbus_vebus_to_pvinverter/test and dbus_vrm/test for other usage examples.
To change a value while testing, without stopping your dummy script and changing its initial value, write
to the dummy data via the dbus. See example.
https://github.com/victronenergy/dbus_vebus_to_pvinverter/tree/master/test
"""
from gi.repository import GLib
import platform
import argparse
import logging
import sys
import os
import subprocess as sp
import json

# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'velib_python'))
from vedbus import VeDbusService
# Should we import and call manually?
# sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'mpp-solar'))

def getInverterData():
    global args
    return json.loads(sp.getoutput("mpp-solar -b {} -P pi30revo -p {} -o json --getstatus".format(args.baudrate, args.serial)))

class DbusMppSolarService(object):
    def __init__(self, servicename, deviceinstance, paths, productname='MPPSolar Inverter', connection='MPPSolar interface'):
        self._dbusservice = VeDbusService(servicename)
        self._paths = paths

        logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 0)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/FirmwareVersion', 0)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)

        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path, settings['initial'], writeable=True, onchangecallback=self._handlechangedvalue)

        GLib.timeout_add(10000, self._update)

    def _update(self):
        try:
            data = getInverterData()
        except e:
            logging.info('Exception: {}'.format(e))
            return True
        logging.info(data)
        with self._dbusservice as s:
            if 'error' in data and 'short' in data['error']:
                s['/Mode'] = 4
                s['/State'] = 0
                s['/Ac/Out/L1/P'] = None
                s['/Ac/In/1/L1/P'] = None
                return True
            
            if 'error' in data and 'battery_voltage' not in data:
                return True # We should exit here
            
            # Normal operation, read data
            s['/Mode'] = 3
            s['/State'] = 9
            if 'battery_voltage' in data:
                s['/Dc/0/Voltage'] = data['battery_voltage'] * 10

            if 'ac_input_voltage' in data:
                s['/Ac/In/1/L1/V'] = data['ac_input_voltage']
            if 'ac_input_frequency' in data:
                s['/Ac/In/1/L1/F'] = data['ac_input_frequency']

            if 'ac_output_voltage' in data:
                s['/Ac/Out/L1/V'] = data['ac_output_voltage']
            if 'ac_output_frequency' in data:
                s['/Ac/Out/L1/F'] = data['ac_output_frequency']
            if 'ac_output_load' in data:
                s['/Ac/Out/L1/P'] = data['ac_output_load']

        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True # accept the change

def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--baudrate","-b", default=2400, type=int)
    parser.add_argument("--serial","-s", required=True, type=str)
    global args
    args = parser.parse_args()

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    output = DbusMppSolarService(
        servicename='com.victronenergy.multi.{}'.format(args.serial.strip("/dev/")),
        deviceinstance=0,
        paths={
            #'/Ac/In/Forward': {'initial': 0, 'update': 1},
            #'/Position': {'initial': 0, 'update': 0},
            #'/Nonupdatingvalue/UseForTestingWritesForExample': {'initial': None},
            #'/DbusInvalid': {'initial': None}

            '/Ac/In/1/L1/V': {'initial': 0},
            #'/Ac/In/1/L2/V': {'initial': 10},
            #'/Ac/In/1/L3/V': {'initial': 10},
            '/Ac/In/1/L1/I': {'initial': 0},
            #'/Ac/In/1/L2/I': {'initial': 10},
            #'/Ac/In/1/L3/I': {'initial': 10},
            '/Ac/In/1/L1/P': {'initial': 0},
            #'/Ac/In/1/L2/P': {'initial': 0.1},
            #'/Ac/In/1/L3/P': {'initial': 0.1},
            '/Ac/In/1/L1/F': {'initial': 0},
            '/Ac/Out/L1/V': {'initial': 0},
            #'/Ac/Out/L2/V': {'initial': 10},
            #'/Ac/Out/L3/V': {'initial': 10},
            '/Ac/Out/L1/I': {'initial': 0},
            #'/Ac/Out/L2/I': {'initial': 10},
            #'/Ac/Out/L3/I': {'initial': 10},
            '/Ac/Out/L1/P': {'initial': 0},
            #'/Ac/Out/L2/P': {'initial': 0.1},
            #'/Ac/Out/L3/P': {'initial': 0.1},
            '/Ac/Out/L1/F': {'initial': 0},
            '/Ac/In/1/Type': {'initial': 1}, #0=Unused;1=Grid;2=Genset;3=Shore
            #'/Ac/In/2/Type': {'initial': 0}, #0=Unused;1=Grid;2=Genset;3=Shore
            '/Ac/In/1/CurrentLimit': {'initial': 10},
            #'/Ac/In/2/CurrentLimit': {'initial': 10},
            '/Ac/NumberOfPhases': {'initial': 1},
            '/Ac/ActiveIn/ActiveInput': {'initial': 0},
            '/Dc/0/Voltage': {'initial': 0},
            '/Dc/0/Current': {'initial': 0},
            #'/Dc/0/Temperature': {'initial': 10},
            #'/Soc': {'initial': 10},
            '/State': {'initial': 0}, #0=Off;1=Low Power;2=Fault;3=Bulk;4=Absorption;5=Float;6=Storage;7=Equalize;8=Passthru;9=Inverting;10=Power assist;11=Power supply;252=External control
            '/Mode': {'initial': 4}, #1=Charger Only;2=Inverter Only;3=On;4=Off
            '/Alarms/HighTemperature': {'initial': 0},
            '/Alarms/HighVoltage': {'initial': 0},
            '/Alarms/HighVoltageAcOut': {'initial': 0},
            '/Alarms/LowTemperature': {'initial': 0},
            '/Alarms/LowVoltage': {'initial': 0},
            '/Alarms/LowVoltageAcOut': {'initial': 0},
            '/Alarms/Overload': {'initial': 0},
            '/Alarms/Ripple': {'initial': 0},
            '/Yield/Power': {'initial': 0},
            '/Yield/User': {'initial': 0},
            #'/Relay/0/State': {'initial': 1},
            '/MppOperationMode': {'initial': 0}, #0=Off;1=Voltage/current limited;2=MPPT active;255=Not available
            '/Pv/V': {'initial': 0},
            '/ErrorCode': {'initial': 0},
            '/Energy/AcIn1ToAcOut': {'initial': 0},
            '/Energy/AcIn1ToInverter': {'initial': 0},
            #'/Energy/AcIn2ToAcOut': {'initial': 0},
            #'/Energy/AcIn2ToInverter': {'initial': 0},
            '/Energy/AcOutToAcIn1': {'initial': 0},
            #'/Energy/AcOutToAcIn2': {'initial': 0},
            '/Energy/InverterToAcIn1': {'initial': 0},
            #'/Energy/InverterToAcIn2': {'initial': 0},
            '/Energy/InverterToAcOut': {'initial': 0},
            '/Energy/OutToInverter': {'initial': 0},
            '/Energy/SolarToAcIn1': {'initial': 0},
            #'/Energy/SolarToAcIn2': {'initial': 0},
            '/Energy/SolarToAcOut': {'initial': 0},
            '/Energy/SolarToBattery': {'initial': 0},
            '/History/Daily/0/Yield': {'initial': 0},
            '/History/Daily/0/MaxPower': {'initial': 0},
            #'/History/Daily/1/Yield': {'initial': 10},
            #'/History/Daily/1/MaxPower': {'initial': 1},
            '/History/Daily/0/Pv/0/Yield': {'initial': 0},
            #'/History/Daily/0/Pv/1/Yield': {'initial': 10},
            #'/History/Daily/0/Pv/2/Yield': {'initial': 10},
            #'/History/Daily/0/Pv/3/Yield': {'initial': 10},
            #'/History/Daily/1/Pv/0/Yield': {'initial': 10},
            #'/History/Daily/1/Pv/1/Yield': {'initial': 10},
            #'/History/Daily/1/Pv/2/Yield': {'initial': 10},
            #'/History/Daily/1/Pv/3/Yield': {'initial': 10},
            '/History/Daily/0/Pv/0/MaxPower': {'initial': 0},
            #'/History/Daily/0/Pv/1/MaxPower': {'initial': 1},
            #'/History/Daily/0/Pv/2/MaxPower': {'initial': 1},
            #'/History/Daily/0/Pv/3/MaxPower': {'initial': 1},
            #'/History/Daily/1/Pv/0/MaxPower': {'initial': 1},
            #'/History/Daily/1/Pv/1/MaxPower': {'initial': 1},
            #'/History/Daily/1/Pv/2/MaxPower': {'initial': 1},
            #'/History/Daily/1/Pv/3/MaxPower': {'initial': 1},
            '/Pv/0/V': {'initial': 0},
            #'/Pv/1/V': {'initial': 10},
            #'/Pv/2/V': {'initial': 10},
            #'/Pv/3/V': {'initial': 10},
            '/Pv/0/P': {'initial': 0},
            #'/Pv/1/P': {'initial': 1},
            #'/Pv/2/P': {'initial': 1},
            #'/Pv/3/P': {'initial': 1},
            '/Alarms/LowSoc': {'initial': 0},
            '/Yield/User': {'initial': 0},
            '/Temperature': {'initial': 123}
        })

    logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()