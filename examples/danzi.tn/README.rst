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

pyhton cavalletto-server.py -n 2 -p 502

-n  number of istances
-p  starting port number (if -n > 1 port number will be increased)


------------------------------------------------------------
pump-server.py
------------------------------------------------------------

pump-server.py  -n 2 -p 502

-n  number of istances
-p  starting port number (if -n > 1 port number will be increased)

------------------------------------------------------------
synchronous-client.py
------------------------------------------------------------

TBD
