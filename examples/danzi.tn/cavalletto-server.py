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
from pymodbus.server.async import StartTcpServer, ModbusServerFactory
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
import os
import sys
import getopt
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
#  MODBUS data numbered N is addressed in the MODBUS PDU N-1
FIRST_REGISTER = 40001 # 40001 primo indirizzo buono (indice 0->40001)
NUM_REGISTERS = 110 # from 0 to 109 (indice 0->reg 1 e 109->reg 110)
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


from pymodbus.transaction import ModbusSocketFramer, ModbusAsciiFramer
from pymodbus.constants import Defaults
def StartMultipleTcpServers(context_list, identity_list=None, address_list=None, console=False, **kwargs):
    ''' Helper method to start the Modbus Async TCP server

    :param context: The server data context
    :param identify: The server identity to use (default empty)
    :param address: An optional (interface, port) to bind to.
    :param console: A flag indicating if you want the debug console
    :param ignore_missing_slaves: True to not send errors on a request to a missing slave
    '''
    from twisted.internet import reactor
    for iter, address  in enumerate(address_list):
        address = address or ("", Defaults.Port)
        context = context_list[iter]
        identity = identity_list[iter]
        framer  = ModbusSocketFramer
        factory = ModbusServerFactory(context, framer, identity, **kwargs)
        if console:
            from pymodbus.internal.ptwisted import InstallManagementConsole
            InstallManagementConsole({'factory': factory})

        log.info("Starting Modbus TCP Server on %s:%s" % address)
        reactor.listenTCP(address[1], factory, interface=address[0])
    reactor.run()

def default_val_factory():
    default_val = [0x00]*NUM_REGISTERS
    # Default pressure as mA
    default_val[0] = 12345
    default_val[4-1] = p_rand.rvs()
    #   as bar
    default_val[5-1] = int(p_func(default_val[4-1])) # p_func returns a float, register is a word 16 bit, it means it can store unsigned short
    # Default flow-rate as mA
    default_val[6-1] = q_rand.rvs()
    #   as lit/min
    default_val[7-1] = int(q_func(default_val[6-1])) # p_func returns a float, register is a word 16 bit, it means it can store unsigned short
    # Low and High for the pressure 
    default_val[104-1] = low_p
    default_val[105-1] = high_p
    # Low and High for the flow-rate 
    default_val[106-1] = low_q
    default_val[107-1] = high_q
    default_val[110-1] = 110
    log.debug("default values: " + str(default_val))
    return default_val

context_dict ={}
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
    srv_id = a[1]
    register = 3 # holding registers
    slave_id = 0x00
    # first register of the modbus slave is 40001
    # gets current values
    START_ADDRESS = FIRST_REGISTER-1 # inizia a leggere da 40000 e prendi gli N successivi,escluso il 40000
    values   = context[slave_id].getValues(register, START_ADDRESS, count=NUM_REGISTERS)
    log.debug("cavalletto context values: " + str(values))
    # update P and Q with random values
    p_new = p_rand.rvs() # as mA
    q_new = q_rand.rvs() # as mA
    log.debug("p_new=%d; q_new=%d" % (p_new,q_new))
    values[4-1] = p_new
    values[5-1] = int(p_func(p_new)) # as bar
    values[6-1] = q_new # as mA
    values[7-1] = int(q_func(q_new)) # as lit/min
    values[110-1] = 999
    log.debug("On cavalletto server %02d new values: %s" %(srv_id, str(values)))
    # assign new values to context
    context[slave_id].setValues(register, START_ADDRESS, values)

def context_factory():
    default_val = default_val_factory()
    #---------------------------------------------------------------------------# 
    # initialize your data store
    #---------------------------------------------------------------------------# 
    store = ModbusSlaveContext(
        di = ModbusSequentialDataBlock(0, [5]*100), 
        co = ModbusSequentialDataBlock(0, [5]*100),
        hr = ModbusSequentialDataBlock(FIRST_REGISTER, default_val), #only holding registers starting from 40001 
        ir = ModbusSequentialDataBlock(0, [5]*100))
    context = ModbusServerContext(slaves=store, single=True)
    return context

#---------------------------------------------------------------------------# 
# initialize the server information
#---------------------------------------------------------------------------# 
def identity_factory():
    identity = ModbusDeviceIdentification()
    identity.VendorName  = 'pymodbus'
    identity.ProductCode = 'PM'
    identity.VendorUrl   = 'http://github.com/andreadanzi/pymodbus/'
    identity.ProductName = 'pymodbus Manifold Server'
    identity.ModelName   = 'pymodbus Manifold Server'
    identity.MajorMinorRevision = '1.0'
    return identity

def main(argv):
    syntax = os.path.basename(__file__) + " -p <first port> -n <number of servers>"
    tcp_port = 502
    no_server = 1
    try:
        opts = getopt.getopt(argv, "hp:n:", ["port=", "noserver="])[0]
    except getopt.GetoptError:
        print syntax
        sys.exit(1)
    if len(opts) < 1:
        print syntax
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print syntax
            sys.exit()
        elif opt in ("-p", "--port"):
            tcp_port = int(arg)
        elif opt in ("-n", "--noserver"):
            no_server = int(arg)
    port = tcp_port
    context_list = []
    identity_list = []
    address_list = []
    for srv in range(no_server):
        address_list.append(("127.0.0.1", port))
        port += 1
        context = context_factory()
        context_list.append(context)
        identity_list.append(identity_factory())
        time = 1 # 1 seconds delay
        loop = LoopingCall(f=updating_writer, a=(context,srv,))
        loop.start(time, now=False) # initially delay by time
    StartMultipleTcpServers(context_list, identity_list, address_list)
    
if __name__ == "__main__":
    main(sys.argv[1:])