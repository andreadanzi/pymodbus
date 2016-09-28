# -*- coding: utf-8 -*-
#!/usr/bin/env python
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
# INIETTORE
pump_host = '10.243.37.106' # 10.243.37.xx
pump_port = 502 # 502
client = ModbusClient(pump_host, port=pump_port)
ret_p=client.connect()
assert(ret_p==True)
default_550 = 2
rq = client.write_register(550,default_550,unit=1)
assert(rq.function_code < 0x80)
rr_p = client.read_holding_registers(500,100,unit=1)
assert(len(rr_p.registers)==100)
for idx, r in enumerate(rr_p.registers):
    print "MW5{0:02d}={1}".format(idx,r)
print rr_p.registers[0]
assert(rr_p.registers[0]==default_550) # registro 500 contiene quanto settato in 550
print "Pump register 500 = {0}".format(rr_p.registers[0])
client.close()
# CAVALLETTO 1
manifold_host = '10.243.37.8' # 10.243.37.xx
manifold_port = 502  # 502
client = ModbusClient(manifold_host, port=manifold_port)
ret_m=client.connect()
assert(ret_m==True)
rr_m = client.read_holding_registers(0,48)
assert(len(rr_m.registers)==48)
assert(rr_m.registers[0]==0x5200)
print "Manifold 1 first register {0}".format(rr_m.registers[0])
sIPAddr = "%d.%d.%d.%d" %  tuple(rr_m.registers[32-1:36-1])
print "Manifold 1 IP address {0}".format(sIPAddr)

rr1 = client.read_holding_registers(103,10)
reg104_1 = tuple(rr1.registers )
print reg104_1
client.close()
# CAVALLETTO 2
ret_m2 = False

manifold_host = '10.243.37.7' # 10.243.37.xx
manifold_port = 502  # 502
client = ModbusClient(manifold_host, port=manifold_port)
ret_m2=client.connect()
assert(ret_m==True)
rr_m = client.read_holding_registers(0,48)
assert(len(rr_m.registers)==48)
assert(rr_m.registers[0]==0x5200)
print "Manifold 2 first register {0}".format(rr_m.registers[0])
sIPAddr = "%d.%d.%d.%d" %  tuple(rr_m.registers[32-1:36-1])
print "Manifold 2 IP address {0}".format(sIPAddr)

rr1 = client.read_holding_registers(103,10)
reg104_1 = tuple(rr1.registers )
print reg104_1

client.close()

print "Pump {0}, Manifold 1 {1},  Manifold 2 {2}: passed!".format(ret_p,ret_m, ret_m2)
