#!/usr/bin/env python
'''
Pymodbus Synchronous Client Examples
--------------------------------------------------------------------------

The following is an example of how to use the synchronous modbus client
implementation from pymodbus.

It should be noted that the client can also be used with
the guard construct that is available in python 2.5 and up::

    with ModbusClient('127.0.0.1') as client:
        result = client.read_coils(1,10)
        print result
'''
#---------------------------------------------------------------------------# 
# import the various server implementations
#---------------------------------------------------------------------------# 
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
#from pymodbus.client.sync import ModbusUdpClient as ModbusClient
#from pymodbus.client.sync import ModbusSerialClient as ModbusClient
from twisted.internet.task import LoopingCall
#---------------------------------------------------------------------------# 
# configure the client logging
#---------------------------------------------------------------------------# 
import logging, time
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

#---------------------------------------------------------------------------# 
# choose the client you want
#---------------------------------------------------------------------------# 
# make sure to start an implementation to hit against. For this
# you can use an existing device, the reference implementation in the tools
# directory, or start a pymodbus server.
#
# If you use the UDP or TCP clients, you can override the framer being used
# to use a custom implementation (say RTU over TCP). By default they use the
# socket framer::
#
#    client = ModbusClient('localhost', port=5020, framer=ModbusRtuFramer)
#
# It should be noted that you can supply an ipv4 or an ipv6 host address for
# both the UDP and TCP clients.
#
# There are also other options that can be set on the client that controls
# how transactions are performed. The current ones are:
#
# * retries - Specify how many retries to allow per transaction (default = 3)
# * retry_on_empty - Is an empty response a retry (default = False)
# * source_address - Specifies the TCP source address to bind to
#
# Here is an example of using these options::
#
#    client = ModbusClient('localhost', retries=3, retry_on_empty=True)
#---------------------------------------------------------------------------# 
client = ModbusClient('127.0.0.1', port=502)
#client = ModbusClient(method='ascii', port='/dev/pts/2', timeout=1)
#client = ModbusClient(method='rtu', port='/dev/pts/2', timeout=1)
client.connect()
log.debug("connected")


def logPump():
    rr = client.read_holding_registers(520,6)
    decoder = BinaryPayloadDecoder.fromRegisters(rr.registers,endian=Endian.Little)
    f_520 = decoder.decode_32bit_float()
    f_522 = decoder.decode_32bit_float()
    f_524 = decoder.decode_32bit_float()
    #log.debug("read values: " + str(rr.registers))
    log.debug("\n#### Readings ####\n##f_520=%f;f_522=%f;f_524=%f\n####" %(f_520, f_522, f_524 ))

def logCavalletto():
    rr = client.read_holding_registers(40001,8)
    log.debug("\n#### Readings ####\n##Pressure \tP(mA)=%d \tP(bar)=%d \n##Flow-rate \tQ(mA)=%d \tQ(lit/min)=%d \n####" %(rr.registers[4], rr.registers[5], rr.registers[6],rr.registers[7] ))
    

    
for i in range(20):
    #logCavalletto()
    logPump()
    time.sleep(1)
log.debug("closing...")

#---------------------------------------------------------------------------# 
# close the client
#---------------------------------------------------------------------------# 
# client.close()
