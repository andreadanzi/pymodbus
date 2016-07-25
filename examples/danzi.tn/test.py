# -*- coding: utf-8 -*-
#!/usr/bin/env python
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
# test cavalletto
client = ModbusClient('localhost', port=502)
client.connect()
# scegliere registro e assert da verificare
rr = client.read_holding_registers(40001,2)
print rr.registers
assert(rr.registers[0] == 0x5100)   # test the expected value (Machine ID, defaukt is 0x5100)
client.close()
# test iniettore
client = ModbusClient('localhost', port=5020)
client.connect()
rr = client.read_holding_registers(40001,2)
print rr.registers
assert(rr.registers[0] == 12345)   # test the expected value (pump test è 12345)
client.close()