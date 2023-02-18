# dbus-mppsolar
DBus VenusOS driver for MPPSolar inverter or compatible one

# INSTRUCTIONS

- Clone GIT & submodules:
  -- git clone --recurse-submodules https://github.com/DarkZeros/dbus-mppsolar /data/etc/dbus-mppsolar
  -- Need velib_python for execution of the service
  -- Need mpp-solar to communicate with Inverter
  -- Install pip & then install mpp-solar package

- PIP & pip install package
  /opt/victronenergy/swupdate-scripts/set-feed.sh release ?
  opkg install python3-pip
  cd mpp-solar; pip3 install .

- Install service
  cp -R /data/etc/dbus-mppsolar/service /opt/victronenergy/service-templates/dbus-mppsolar

- Add service to  /etc/venus/serial-starter.conf:
...
service mppsolar        dbus-mppsolar
alias   default         gps:vedirect:mppsolar 
...