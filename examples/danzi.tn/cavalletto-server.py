# -*- coding: utf-8 -*-
#!/usr/bin/env python
'''
Pymodbus Server With Updating Thread
--------------------------------------------------------------------------

This is an example of having a background thread updating the
context while the server is operating. This can also be done with
a python thread::

    from threading import Thread

    thread = Thread(target=updating_writer, args=(context,))
    thread.start()
'''
#---------------------------------------------------------------------------# 
# import the modbus libraries we need
#---------------------------------------------------------------------------# 
from pymodbus.server.async import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.transaction import ModbusRtuFramer, ModbusAsciiFramer

#---------------------------------------------------------------------------# 
# import the twisted libraries we need
#---------------------------------------------------------------------------# 
from twisted.internet.task import LoopingCall

#---------------------------------------------------------------------------# 
# configure the service logging
#---------------------------------------------------------------------------# 
import logging
import logging.handlers
# logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)
file_handler = logging.handlers.RotatingFileHandler("cavalletto-server.log", maxBytes=5000000,backupCount=5)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)


#---------------------------------------------------------------------------# 
# define default values
#---------------------------------------------------------------------------# 
from scipy.stats import randint
import numpy as np
import struct
low, high = 4, 20 # current as milliampere mA - analogic values
low_p, high_p = 0, 100 # pressure (P in bar)
low_q, high_q = 5, 50 # flow-rate (Q in lit/min)
first_register = 0x9C41 # 40001 - 0x9C41 as hex
num_registers = 110 # max num of registers
default_val = [0x00]*num_registers

# uniform discrete random variables for simulating pressure and flow-rate
p_rand = randint(low, high) # pressure
q_rand = randint(low, high) # flow rate

# Least squares polynomial (linear) fit. 
#   Conversion from current (mA) to pressure (bar)
p_fit = np.polyfit([low, high],[low_p, high_p],1)
p_func = np.poly1d(p_fit)
#   Conversion from current (mA) to flow-rate (lit/min)
q_fit = np.polyfit([low, high],[low_q, high_q],1)
q_func = np.poly1d(q_fit)
# Default pressure as mA
default_val[4] = p_rand.rvs()
#   as bar
default_val[5] = int(p_func(default_val[4])) # p_func returns a float, register is a word 16 bit, it means it can store unsigned short
# Default flow-rate as mA
default_val[6] = q_rand.rvs()
#   as lit/min
default_val[7] = int(q_func(default_val[6])) # p_func returns a float, register is a word 16 bit, it means it can store unsigned short
# Low and High for the pressure 
default_val[104] = low_p
default_val[105] = high_p
# Low and High for the flow-rate 
default_val[106] = low_q
default_val[107] = high_q
log.debug("default values: " + str(default_val))
#---------------------------------------------------------------------------# 
# define the callback process updating registers
#---------------------------------------------------------------------------# 
def updating_writer(a):
    ''' A worker process that runs every so often and
    updates live values of the context. 

    :param arguments: The input arguments to the call
    '''
    log.debug("updating the manifold context")
    context  = a[0]
    register = 3 # holding registers
    slave_id = 0x00
    # first register of the modbus slave is 40001
    address  = first_register
    # gets current values
    values   = context[slave_id].getValues(register, address, count=num_registers)
    # update P and Q with random values
    values[4] = p_rand.rvs() # as mA
    values[5] = int(p_func(values[4])) # as bar
    values[6] = q_rand.rvs() # as mA
    values[7] = int(q_func(values[6])) # as lit/min
    log.debug("new values: " + str(values))
    # assign new values to context
    context[slave_id].setValues(register, address, values)

#---------------------------------------------------------------------------# 
# initialize your data store
#---------------------------------------------------------------------------# 
store = ModbusSlaveContext(
    di = ModbusSequentialDataBlock(0, [5]*100), 
    co = ModbusSequentialDataBlock(0, [5]*100),
    hr = ModbusSequentialDataBlock(first_register, default_val), #only holding registers starting from 40001 
    ir = ModbusSequentialDataBlock(0, [5]*100), zero_mode=True)
context = ModbusServerContext(slaves=store, single=True)

#---------------------------------------------------------------------------# 
# initialize the server information
#---------------------------------------------------------------------------# 
identity = ModbusDeviceIdentification()
identity.VendorName  = 'pymodbus'
identity.ProductCode = 'PM'
identity.VendorUrl   = 'http://github.com/andreadanzi/pymodbus/'
identity.ProductName = 'pymodbus Manifold Server'
identity.ModelName   = 'pymodbus Manifold Server'
identity.MajorMinorRevision = '1.0'

#---------------------------------------------------------------------------# 
# run the server you want
#---------------------------------------------------------------------------# 
time = 1 # 1 seconds delay
loop = LoopingCall(f=updating_writer, a=(context,))
loop.start(time, now=False) # initially delay by time
# set the IP address properly: change localhost with IPv4 address
StartTcpServer(context, identity=identity, address=("127.0.0.1", 502))
