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
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


#---------------------------------------------------------------------------# 
# define default values
#---------------------------------------------------------------------------# 
from scipy.stats import randint
import numpy as np
import struct
low, high = 4, 20 # mA
low_p, high_p = 0, 100 # pressure (P in bar)
low_q, high_q = 5, 50 # flow-rate (Q in lit/min)
first_register = 0x9C41 # 40001
num_registers = 110
default_val = [0x00]*num_registers
# uniform discrete random variables for pressure and flow-rate
p_rand = randint(low, high)
q_rand = randint(low, high)
# Least squares polynomial (linear) fit
p_fit = np.polyfit([low, high],[low_p, high_p],1)
q_fit = np.polyfit([low, high],[low_q, high_q],1)
# Convertion functions from mV to pressure and flow-rate 
p_func = np.poly1d(p_fit)
q_func = np.poly1d(q_fit)
default_val[4] = p_rand.rvs()
default_val[5] = int(p_func(default_val[4])) # Verificare se mi passano un int 16 bit o cosa
default_val[6] = q_rand.rvs()
default_val[7] = int(q_func(default_val[6])) # Verificare se mi passano un int 16 bit o cosa
default_val[104] = low_p
default_val[105] = high_p
default_val[106] = low_q
default_val[107] = high_q
#---------------------------------------------------------------------------# 
# define your callback process
#---------------------------------------------------------------------------# 
def updating_writer(a):
    ''' A worker process that runs every so often and
    updates live values of the context. It should be noted
    that there is a race condition for the update.

    :param arguments: The input arguments to the call
    '''
    log.debug("updating the context")
    context  = a[0]
    register = 3
    slave_id = 0x00
    address  = first_register
    # gets current values
    values   = context[slave_id].getValues(register, address, count=num_registers)
    # update P and Q with random values
    values[4] = p_rand.rvs()
    values[5] = int(p_func(values[4]))
    values[6] = q_rand.rvs()
    values[7] = int(q_func(values[6]))
    log.debug("new values: " + str(values))
    # assign new values to context
    context[slave_id].setValues(register, address, values)

#---------------------------------------------------------------------------# 
# initialize your data store
#---------------------------------------------------------------------------# 
store = ModbusSlaveContext(
    di = ModbusSequentialDataBlock(0, [5]*100),
    co = ModbusSequentialDataBlock(0, [5]*100),
    hr = ModbusSequentialDataBlock(first_register, default_val), #0x9C41 40001 
    ir = ModbusSequentialDataBlock(0, [5]*100))
context = ModbusServerContext(slaves=store, single=True)

#---------------------------------------------------------------------------# 
# initialize the server information
#---------------------------------------------------------------------------# 
identity = ModbusDeviceIdentification()
identity.VendorName  = 'pymodbus'
identity.ProductCode = 'PM'
identity.VendorUrl   = 'http://github.com/bashwork/pymodbus/'
identity.ProductName = 'pymodbus Server'
identity.ModelName   = 'pymodbus Server'
identity.MajorMinorRevision = '1.0'

#---------------------------------------------------------------------------# 
# run the server you want
#---------------------------------------------------------------------------# 
time = 1 # 1 seconds delay
loop = LoopingCall(f=updating_writer, a=(context,))
loop.start(time, now=False) # initially delay by time
StartTcpServer(context, identity=identity, address=("localhost", 5020))
