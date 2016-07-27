# -*- coding: utf-8 -*-
#!/usr/bin/env python
'''
python cavalletto-server.py -p 5020 -n 1
'''
#---------------------------------------------------------------------------# 
# import the modbus libraries we need
#---------------------------------------------------------------------------# 
from pymodbus.server.async import ModbusServerFactory
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext

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

low, high = 4, 20 # current as milliampere mA - analogic values
low_p, high_p = 0, 100 # pressure (P in bar)
low_q, high_q = 5, 50 # flow-rate (Q in lit/min)
#  MODBUS data numbered N is addressed in the MODBUS PDU N-1
FIRST_REGISTER = 40001 # 40001 primo indirizzo buono (indice 0->40001)
NUM_REGISTERS = 120 # from 0 to 109 (indice 0->reg 1 e 109->reg 110)
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

import socket

offset_rand = randint(10,12)
f0 = 0.05
phi = np.pi/2
A = 5.
def sinFunc(t):
    return A * np.sin(2 * np.pi * f0 * t + phi) + offset_rand.rvs()


def cosFunc(t):
    return A * np.cos(2 * np.pi * f0 * t + phi) + offset_rand.rvs()

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(('8.8.8.8', 0))
s.setblocking(False)
local_ip_address = s.getsockname()[0]
print(local_ip_address)  # prints 10.0.2.40
local_ip_address_splitted = local_ip_address.split(".")

from pymodbus.transaction import ModbusSocketFramer
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
    default_val[0] = 0x5100 # 20736
    default_val[4-1] = p_rand.rvs()
    #   as bar
    default_val[5-1] = int(p_func(default_val[4-1])) # p_func returns a float, register is a word 16 bit, it means it can store unsigned short
    # Default flow-rate as mA
    default_val[6-1] = q_rand.rvs()
    #   as lit/min
    default_val[7-1] = int(q_func(default_val[6-1])) # p_func returns a float, register is a word 16 bit, it means it can store unsigned short
    # IP ADDR. 0 Actual IP address, 1st number Unsigned 16 bits R
    default_val[32-1] = int(local_ip_address_splitted[0])
    # IP ADDR. 1 Actual IP address, 2nd number Unsigned 16 bits R
    default_val[33-1] = int(local_ip_address_splitted[1])
    # IP ADDR. 2 Actual IP address, 3rd number Unsigned 16 bits R
    default_val[34-1] = int(local_ip_address_splitted[2])
    # IP ADDR. 3 Actual IP address, 4th number Unsigned 16 bits R
    default_val[35-1] = int(local_ip_address_splitted[3])
    # AIN1 Low and High for the pressure 
    default_val[104-1] = low
    default_val[105-1] = high
    # AIN1 ENG Low and High for the pressure 
    default_val[106-1] = low_p
    default_val[107-1] = high_p
    # AIN2 Low and High for the flow-rate 
    default_val[110-1] = low
    default_val[111-1] = high
    # AIN2 ENG Low and High for the flow-rate  
    default_val[112-1] = low_q
    default_val[113-1] = high_q
    
    default_val[120-1] = 110
    log.debug("default values: " + str(default_val))
    return default_val

context_dict ={}
#---------------------------------------------------------------------------# 
# define the callback process updating registers
#---------------------------------------------------------------------------# 
g_Time = 0.
def updating_writer(a):
    ''' A worker process that runs every so often and
    updates live values of the context. 

    :param arguments: The input arguments to the call
    '''
    global g_Time    
    g_Time += 1.
    log.debug("updating the manifold context")
    context  = a[0]
    srv_id = a[1]    
    register = 3 # holding registers
    slave_id = 0x00
    # first register of the modbus slave is 40001
    # gets current values
    if context[slave_id].zero_mode:
        START_ADDRESS = FIRST_REGISTER   # if zero_mode=True
    else:
        START_ADDRESS = FIRST_REGISTER-1 # if zero_mode=False. inizia a leggere da 40000 e prendi gli N successivi,escluso il 40000
    values   = context[slave_id].getValues(register, START_ADDRESS, count=NUM_REGISTERS)
    log.debug("cavalletto context values: " + str(values))
    # update P and Q with random values
    #p_new = p_rand.rvs() # as mA
    p_new = sinFunc(g_Time)
    # q_new = q_rand.rvs() # as mA
    q_new = cosFunc(g_Time)
    log.debug("p_new=%d; q_new=%d" % (p_new,q_new))
    values[4-1] = p_new
    values[5-1] = int(p_func(p_new)) # as bar
    values[6-1] = q_new # as mA
    values[7-1] = int(q_func(q_new)) # as lit/min
    values[120-1] = 999
    log.debug("On cavalletto server %02d new values: %s" %(srv_id, str(values)))
    # assign new values to context
    context[slave_id].setValues(register, START_ADDRESS, values)

def context_factory():
    default_val = default_val_factory()
    #---------------------------------------------------------------------------# 
    # initialize your data store
    #
    # The slave context can also be initialized in zero_mode which means that a
    # request to address(0-7) will map to the address (0-7). The default is
    # False which is based on section 4.4 of the specification, so address(0-7)
    # will map to (1-8)::
    #
    #     store = ModbusSlaveContext(..., zero_mode=True)
    #---------------------------------------------------------------------------# 
    store = ModbusSlaveContext(
        di = ModbusSequentialDataBlock(0, [5]*100), 
        co = ModbusSequentialDataBlock(0, [5]*100),
        hr = ModbusSequentialDataBlock(FIRST_REGISTER, default_val), #only holding registers starting from 40001 
        ir = ModbusSequentialDataBlock(0, [5]*100),zero_mode=True)
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