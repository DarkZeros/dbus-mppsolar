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

# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'velib_python'))
from vedbus import VeDbusService

class DbusVevorService(object):
    def __init__(self, servicename, deviceinstance, paths, productname='Dummy product', connection='Dummy service'):
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

        GLib.timeout_add(1000, self._update)

    def _update(self):
        logging.debug("Updating!")
        with self._dbusservice as s:
            for path, settings in self._paths.items():
                if 'update' in settings:
                    update = settings['update']
                    if callable(update):
                        s[path] = update(path, s[path])
                    else:
                        s[path] += update
                    logging.debug("%s: %s" % (path, s[path]))
        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True # accept the change


# === All code below is to simply run it from the commandline for debugging purposes ===

# It will created a dbus service called com.victronenergy.pvinverter.output.
# To try this on commandline, start this program in one terminal, and try these commands
# from another terminal:
# dbus com.victronenergy.pvinverter.output
# dbus com.victronenergy.pvinverter.output /Ac/Energy/Forward GetValue
# dbus com.victronenergy.pvinverter.output /Ac/Energy/Forward SetValue %20
#
# Above examples use this dbus client: http://code.google.com/p/dbus-tools/wiki/DBusCli
# See their manual to explain the % in %20

def main():
    logging.basicConfig(level=logging.DEBUG)

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    output = DbusVevorService(
        servicename='com.victronenergy.multi.tty01',
        deviceinstance=0,
        paths={
            #'/Ac/In/Forward': {'initial': 0, 'update': 1},
            #'/Position': {'initial': 0, 'update': 0},
            #'/Nonupdatingvalue/UseForTestingWritesForExample': {'initial': None},
            #'/DbusInvalid': {'initial': None}

            #/Ac/In/1/L1/V,d,V AC,4500,uint16,10,R
            #/Ac/In/1/L2/V,d,V AC,4501,uint16,10,R
            #/Ac/In/1/L3/V,d,V AC,4502,uint16,10,R
            #/Ac/In/1/L1/I,d,A AC,4503,uint16,10,R
            #/Ac/In/1/L2/I,d,A AC,4504,uint16,10,R
            #/Ac/In/1/L3/I,d,A AC,4505,uint16,10,R
            #/Ac/In/1/L1/P,d,W,4506,int16,0.1,R
            #/Ac/In/1/L2/P,d,W,4507,int16,0.1,R
            #/Ac/In/1/L3/P,d,W,4508,int16,0.1,R
            #/Ac/In/1/L1/F,d,Hz,4509,uint16,100,R
            #/Ac/Out/L1/V,d,V AC,4510,uint16,10,R
            #/Ac/Out/L2/V,d,V AC,4511,uint16,10,R
            #/Ac/Out/L3/V,d,V AC,4512,uint16,10,R
            #/Ac/Out/L1/I,d,A AC,4513,uint16,10,R
            #/Ac/Out/L2/I,d,A AC,4514,uint16,10,R
            #/Ac/Out/L3/I,d,A AC,4515,uint16,10,R
            #/Ac/Out/L1/P,d,W,4516,int16,0.1,R
            #/Ac/Out/L2/P,d,W,4517,int16,0.1,R
            #/Ac/Out/L3/P,d,W,4518,int16,0.1,R
            #/Ac/Out/L1/F,d,Hz,4519,uint16,100,R
            #/Ac/In/1/Type,u,0=Unused;1=Grid;2=Genset;3=Shore,4520,uint16,1,R
            #/Ac/In/2/Type,u,0=Unused;1=Grid;2=Genset;3=Shore,4521,uint16,1,R
            #/Ac/In/1/CurrentLimit,d,A,4522,uint16,10,W
            #/Ac/In/2/CurrentLimit,d,A,4523,uint16,10,W
            #/Ac/NumberOfPhases,u,count,4524,uint16,1,R
            #/Ac/ActiveIn/ActiveInput,u,0=AC Input 1;1=AC Input 2;240=Disconnected,4525,uint16,1,R
            #/Dc/0/Voltage,d,V DC,4526,uint16,100,R
            #/Dc/0/Current,d,A DC,4527,int16,10,R
            #/Dc/0/Temperature,d,Degrees celsius,4528,int16,10,R
            #/Soc,d,%,4529,uint16,10,R
            #/State,u,0=Off;1=Low Power;2=Fault;3=Bulk;4=Absorption;5=Float;6=Storage;7=Equalize;8=Passthru;9=Inverting;10=Power assist;11=Power supply;252=External control,4530,uint16,1,R
            #/Mode,u,1=Charger Only;2=Inverter Only;3=On;4=Off,4531,uint16,1,W
            #/Alarms/HighTemperature,u,0=Ok;1=Warning;2=Alarm,4532,uint16,1,R
            #/Alarms/HighVoltage,u,0=Ok;1=Warning;2=Alarm,4533,uint16,1,R
            #/Alarms/HighVoltageAcOut,u,0=Ok;1=Warning;2=Alarm,4534,uint16,1,R
            #/Alarms/LowTemperature,u,0=Ok;1=Warning;2=Alarm,4535,uint16,1,R
            #/Alarms/LowVoltage,u,0=Ok;1=Warning;2=Alarm,4536,uint16,1,R
            #/Alarms/LowVoltageAcOut,u,0=Ok;1=Warning;2=Alarm,4537,uint16,1,R
            #/Alarms/Overload,u,0=Ok;1=Warning;2=Alarm,4538,uint16,1,R
            #/Alarms/Ripple,u,0=Ok;1=Warning;2=Alarm,4539,uint16,1,R
            #/Yield/Power,d,W,4540,uint16,1,R
            #/Yield/User,d,kWh,4541,uint16,10,R
            #/Relay/0/State,i,0=Open;1=Closed,4542,uint16,1,R
            #/MppOperationMode,i,0=Off;1=Voltage/current limited;2=MPPT active;255=Not available,4543,uint16,1,R
            #/Pv/V,d,V DC,4544,uint16,10,R
            #/ErrorCode,i,0=No error;1=Battery temperature too high;2=Battery voltage too high;3=Battery temperature sensor miswired (+);4=Battery temperature sensor miswired (-);5=Battery temperature sensor disconnected;6=Battery voltage sense miswired (+);7=Battery voltage sense miswired (-);8=Battery voltage sense disconnected;9=Battery voltage wire losses too high;17=Charger temperature too high;18=Charger over-current;19=Charger current polarity reversed;20=Bulk time limit reached;22=Charger temperature sensor miswired;23=Charger temperature sensor disconnected;34=Input current too high,4545,uint16,1,R
            #/Energy/AcIn1ToAcOut,d,kWh,4546,uint32,100,R
            #/Energy/AcIn1ToInverter,d,kWh,4548,uint32,100,R
            #/Energy/AcIn2ToAcOut,d,kWh,4550,uint32,100,R
            #/Energy/AcIn2ToInverter,d,kWh,4552,uint32,100,R
            #/Energy/AcOutToAcIn1,d,kWh,4554,uint32,100,R
            #/Energy/AcOutToAcIn2,d,kWh,4556,uint32,100,R
            #/Energy/InverterToAcIn1,d,kWh,4558,uint32,100,R
            #/Energy/InverterToAcIn2,d,kWh,4560,uint32,100,R
            #/Energy/InverterToAcOut,d,kWh,4562,uint32,100,R
            #/Energy/OutToInverter,d,kWh,4564,uint32,100,R
            #/Energy/SolarToAcIn1,d,kWh,4566,uint32,100,R
            #/Energy/SolarToAcIn2,d,kWh,4568,uint32,100,R
            #/Energy/SolarToAcOut,d,kWh,4570,uint32,100,R
            #/Energy/SolarToBattery,d,kWh,4572,uint32,100,R
            #/History/Daily/0/Yield,d,kWh,4574,uint16,10,R
            #/History/Daily/0/MaxPower,d,W,4575,uint16,1,R
            #/History/Daily/1/Yield,d,kWh,4576,uint16,10,R
            #/History/Daily/1/MaxPower,d,W,4577,uint16,1,R
            #/History/Daily/0/Pv/0/Yield,d,kWh,4578,uint16,10,R
            #/History/Daily/0/Pv/1/Yield,d,kWh,4579,uint16,10,R
            #/History/Daily/0/Pv/2/Yield,d,kWh,4580,uint16,10,R
            #/History/Daily/0/Pv/3/Yield,d,kWh,4581,uint16,10,R
            #/History/Daily/1/Pv/0/Yield,d,kWh,4582,uint16,10,R
            #/History/Daily/1/Pv/1/Yield,d,kWh,4583,uint16,10,R
            #/History/Daily/1/Pv/2/Yield,d,kWh,4584,uint16,10,R
            #/History/Daily/1/Pv/3/Yield,d,kWh,4585,uint16,10,R
            #/History/Daily/0/Pv/0/MaxPower,d,W,4586,uint16,1,R
            #/History/Daily/0/Pv/1/MaxPower,d,W,4587,uint16,1,R
            #/History/Daily/0/Pv/2/MaxPower,d,W,4588,uint16,1,R
            #/History/Daily/0/Pv/3/MaxPower,d,W,4589,uint16,1,R
            #/History/Daily/1/Pv/0/MaxPower,d,W,4590,uint16,1,R
            #/History/Daily/1/Pv/1/MaxPower,d,W,4591,uint16,1,R
            #/History/Daily/1/Pv/2/MaxPower,d,W,4592,uint16,1,R
            #/History/Daily/1/Pv/3/MaxPower,d,W,4593,uint16,1,R
            #/Pv/0/V,d,V DC,4594,uint16,10,R
            #/Pv/1/V,d,V DC,4595,uint16,10,R
            #/Pv/2/V,d,V DC,4596,uint16,10,R
            #/Pv/3/V,d,V DC,4597,uint16,10,R
            #/Pv/0/P,d,W,4598,uint16,1,R
            #/Pv/1/P,d,W,4599,uint16,1,R
            #/Pv/2/P,d,W,4600,uint16,1,R
            #/Pv/3/P,d,W,4601,uint16,1,R
            #/Alarms/LowSoc,u,,4602,uint16,1,R
            #/Yield/User,d,kWh,4603,uint32,1,R


            '/Ac/In/1/L1/V': {'initial': 10},
            '/Ac/In/1/L2/V': {'initial': 10},
            '/Ac/In/1/L3/V': {'initial': 10},
            '/Ac/In/1/L1/I': {'initial': 10},
            '/Ac/In/1/L2/I': {'initial': 10},
            '/Ac/In/1/L3/I': {'initial': 10},
            '/Ac/In/1/L1/P': {'initial': 0.1},
            '/Ac/In/1/L2/P': {'initial': 0.1},
            '/Ac/In/1/L3/P': {'initial': 0.1},
            '/Ac/In/1/L1/F': {'initial': 100},
            '/Ac/Out/L1/V': {'initial': 10},
            '/Ac/Out/L2/V': {'initial': 10},
            '/Ac/Out/L3/V': {'initial': 10},
            '/Ac/Out/L1/I': {'initial': 10},
            '/Ac/Out/L2/I': {'initial': 10},
            '/Ac/Out/L3/I': {'initial': 10},
            '/Ac/Out/L1/P': {'initial': 0.1},
            '/Ac/Out/L2/P': {'initial': 0.1},
            '/Ac/Out/L3/P': {'initial': 0.1},
            '/Ac/Out/L1/F': {'initial': 100},
            '/Ac/In/1/Type': {'initial': 1},
            '/Ac/In/2/Type': {'initial': 1},
            '/Ac/In/1/CurrentLimit': {'initial': 10},
            '/Ac/In/2/CurrentLimit': {'initial': 10},
            '/Ac/NumberOfPhases': {'initial': 1},
            '/Ac/ActiveIn/ActiveInput': {'initial': 1},
            '/Dc/0/Voltage': {'initial': 100},
            '/Dc/0/Current': {'initial': 10},
            '/Dc/0/Temperature': {'initial': 10},
            '/Soc': {'initial': 10},
            '/State': {'initial': 1},
            '/Mode': {'initial': 1},
            '/Alarms/HighTemperature': {'initial': 1},
            '/Alarms/HighVoltage': {'initial': 1},
            '/Alarms/HighVoltageAcOut': {'initial': 1},
            '/Alarms/LowTemperature': {'initial': 1},
            '/Alarms/LowVoltage': {'initial': 1},
            '/Alarms/LowVoltageAcOut': {'initial': 1},
            '/Alarms/Overload': {'initial': 1},
            '/Alarms/Ripple': {'initial': 1},
            '/Yield/Power': {'initial': 1},
            '/Yield/User': {'initial': 10},
            '/Relay/0/State': {'initial': 1},
            '/MppOperationMode': {'initial': 1},
            '/Pv/V': {'initial': 10},
            '/ErrorCode': {'initial': 1},
            '/Energy/AcIn1ToAcOut': {'initial': 100},
            '/Energy/AcIn1ToInverter': {'initial': 100},
            '/Energy/AcIn2ToAcOut': {'initial': 100},
            '/Energy/AcIn2ToInverter': {'initial': 100},
            '/Energy/AcOutToAcIn1': {'initial': 100},
            '/Energy/AcOutToAcIn2': {'initial': 100},
            '/Energy/InverterToAcIn1': {'initial': 100},
            '/Energy/InverterToAcIn2': {'initial': 100},
            '/Energy/InverterToAcOut': {'initial': 100},
            '/Energy/OutToInverter': {'initial': 100},
            '/Energy/SolarToAcIn1': {'initial': 100},
            '/Energy/SolarToAcIn2': {'initial': 100},
            '/Energy/SolarToAcOut': {'initial': 100},
            '/Energy/SolarToBattery': {'initial': 100},
            '/History/Daily/0/Yield': {'initial': 10},
            '/History/Daily/0/MaxPower': {'initial': 1},
            '/History/Daily/1/Yield': {'initial': 10},
            '/History/Daily/1/MaxPower': {'initial': 1},
            '/History/Daily/0/Pv/0/Yield': {'initial': 10},
            '/History/Daily/0/Pv/1/Yield': {'initial': 10},
            '/History/Daily/0/Pv/2/Yield': {'initial': 10},
            '/History/Daily/0/Pv/3/Yield': {'initial': 10},
            '/History/Daily/1/Pv/0/Yield': {'initial': 10},
            '/History/Daily/1/Pv/1/Yield': {'initial': 10},
            '/History/Daily/1/Pv/2/Yield': {'initial': 10},
            '/History/Daily/1/Pv/3/Yield': {'initial': 10},
            '/History/Daily/0/Pv/0/MaxPower': {'initial': 1},
            '/History/Daily/0/Pv/1/MaxPower': {'initial': 1},
            '/History/Daily/0/Pv/2/MaxPower': {'initial': 1},
            '/History/Daily/0/Pv/3/MaxPower': {'initial': 1},
            '/History/Daily/1/Pv/0/MaxPower': {'initial': 1},
            '/History/Daily/1/Pv/1/MaxPower': {'initial': 1},
            '/History/Daily/1/Pv/2/MaxPower': {'initial': 1},
            '/History/Daily/1/Pv/3/MaxPower': {'initial': 1},
            '/Pv/0/V': {'initial': 10},
            '/Pv/1/V': {'initial': 10},
            '/Pv/2/V': {'initial': 10},
            '/Pv/3/V': {'initial': 10},
            '/Pv/0/P': {'initial': 1},
            '/Pv/1/P': {'initial': 1},
            '/Pv/2/P': {'initial': 1},
            '/Pv/3/P': {'initial': 1},
            '/Alarms/LowSoc': {'initial': 1},
            '/Yield/User': {'initial': 1}
        })

    logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()