============================================================
Modbus TCP BGU and Manifold slaves simumlator
============================================================

There are a three different python modules

- cavalletto-server.py: simulates a manifold slave with pressure transducer and flow-meter
- pump-server.py: simulates the pump slave
- synchronous-client.py: a simple synchronous master that sends messages to slaves

Install python 2.7 anaconda distro from https://www.continuum.io/downloads

Once python is installed, install pymodbus

>cd <path>/pymodbus
>python setup.py install

------------------------------------------------------------
cavalletto-server.py
------------------------------------------------------------

pyhton cavalletto-server.py

INFO:pymodbus.server.async:Starting Modbus TCP Server on localhost:5020
DEBUG:root:updating the manifold context
DEBUG:pymodbus.datastore.context:getValues[3] 40002:110

------------------------------------------------------------
pump-server.py
------------------------------------------------------------

TBD

------------------------------------------------------------
synchronous-client.py
------------------------------------------------------------

TBD
