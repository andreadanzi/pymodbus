# -*- coding: utf-8 -*-
#!/usr/bin/env python
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
# CAVALLETTO P1
pump_host = '10.243.37.8' # 16-43-008
pump_port = 502 # 502
client = ModbusClient(pump_host, port=pump_port)
ret_p=client.connect()
assert(ret_p==True)
client.close()
# CAVALLETTO P2
ret_m2 = False
"""
manifold_host = '10.243.37.7' # 16-43-007
manifold_port = 502  # 502
client = ModbusClient(manifold_host, port=manifold_port)
ret_m2=client.connect()
assert(ret_m2==True)
client.close()
"""
# INIETTORE

manifold_host = '10.243.37.101' # 10.243.37.xx
manifold_port = 502  # 502
client = ModbusClient(manifold_host, port=manifold_port)
ret_m1=client.connect()
assert(ret_m1==True)
client.close()
print "Manifold 1 {0}, Manifold 2 {1}, Pump {2}: passed!".format(ret_p,ret_m2, ret_m1)
