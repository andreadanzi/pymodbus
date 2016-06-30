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
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder

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
first_register = 0x1F4 # 500
num_registers = 100 # from 500 to 599
liters_cycle = 2.42 # 230(103-50.2) - 230 corsa, 103 diam. esterno, 50.2 diam interno
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
# DA 500 A 549 DATI SCRITTI DA PLC POMPE
default_val[0] = 1 # APP_PER VERIFICA COMUNICAZIONE
default_val[2] = 1 # STATO MACCHINA 1 ( IN BIT )
default_val[3] = 1 # %MW503 STATO MACCHINA 2 ( IN BIT )
default_val[4] = 1 # %MW504 ALLARMI MACHINA 1 ( IN BIT )
default_val[5] = 1 # %MW505 ALLARMI MACHINA 2 ( IN BIT )
default_val[6] = 1 # %MW506 COPIA STATO COMANDO REMOTO 1 MOMENTANEO ( bit )
default_val[7] = 1 # %MW507 COPIA STATO COMANDO REMOTO 2 MOMENTANEO ( bit )
default_val[8] = 1 # %MW508 COPIA STATO COMANDO REMOTO 1 CONTINUO ( bit )
default_val[9] = 1 # %MW509 COPIA STATO COMANDO REMOTO 2 CONTINUO ( bit )
default_val[12] = 1 # %MW512 TEMPO DI ATTIVITA' DELLA POMPA
default_val[13] = 1 # %MW513 TEMPO DI ATTIVITA' DELLA POMPA INIETTORE
default_val[14] = 2 # %MW514 TEMPO DI ATTIVITA' DELLA POMPA GIORNALIERO
default_val[15] = 2 # %MW515 TEMPO DI ATTIVITA' DELLA INIETTORE GIORNALIERO
default_val[16] = int(p_func(p_rand.rvs())) # %MW516 PRESSIONE ATTUALE
default_val[17] = 3 # %MW517 
default_val[18] = 4 # %MW518 
default_val[19] = 4 # %MW519 
q_default = q_func(q_rand.rvs())
q_m_ch = 60.0*q_default/1000.0
cicli_default = q_default*liters_cycle
# conversione float - Endian.Little il primo è il meno significativo
builder = BinaryPayloadBuilder(endian=Endian.Little)
builder.add_32bit_float(q_default)
builder.add_32bit_float(q_m_ch)
builder.add_32bit_float(cicli_default)
reg=builder.to_registers()
default_val[20:26]=reg
"""
default_val[20] = reg[0] # %MW520 CICLI / MINUTO
default_val[21] = reg[1] # %MW521 
default_val[22] = reg[2] # %MF522 LITRI / MINUTO
default_val[23] = reg[3] #  
default_val[24] = reg[4] # %MF524 MC / ORA
default_val[25] = reg[5] #  
"""
# DA 550 A 599 DATI LETTI DA PLC POMPE
default_val[50] = 1 # %MW550 CONTATORE PER VERIFICA COMUNICAZIONE
default_val[51] = 1 # %MW551 
default_val[52] = 2 # %MW552 COMANDO MACCHINA DA REMOTO 1 MOMENTANEO ( bit )
default_val[53] = 2 # %MW553 COMANDO MACCHINA DA REMOTO 2 MOMENTANEO ( bit )
default_val[54] = 3 # %MW554 COMANDO MACCHINA DA REMOTO 1 CONTINUO ( bit )
default_val[55] = 3 # %MW555 COMANDO MACCHINA DA REMOTO 2 CONTINUO ( bit )
default_val[56] = 4 # %MW556 
default_val[57] = 4 # %MW557 
default_val[58] = 5 # %MW558 
default_val[59] = 5 # %MW559 
default_val[60] = 30 # %MW560 COMANDO BAR DA REMOTO
default_val[61] = 6 # %MW561 
default_val[62] = 10 # %MW562 COMANDO NUMERO CICLI MINUTO DA REMOTO
log.debug("default values: " + str(default_val))
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
    values[16] = int(p_func(p_rand.rvs())) # %MW516 PRESSIONE ATTUALE
    q_val = q_func(q_rand.rvs())
    q_m_ch = 60.0*q_val/1000.0
    cicli = q_val*liters_cycle
    log.debug("q=%f, mc=%f, cicli=%f" % (q_val,q_m_ch,cicli))
    # conversione float - Endian.Little il primo è il meno significativo
    builder = BinaryPayloadBuilder(endian=Endian.Little)
    builder.add_32bit_float(q_val)
    builder.add_32bit_float(q_m_ch)
    builder.add_32bit_float(cicli)
    reg=builder.to_registers()
    values[20:26]=reg
    """
    values[20] = cicli # %MW520 CICLI / MINUTO
    values[22] = q_val # %MF522 LITRI / MINUTO
    values[24] = q_m_ch # %MF524 MC / ORA
    """
    log.debug("new values: " + str(values[20:26]))
    # assign new values to context
    context[slave_id].setValues(register, address, values)

#---------------------------------------------------------------------------# 
# initialize your data store
#---------------------------------------------------------------------------# 
store = ModbusSlaveContext(
    di = ModbusSequentialDataBlock(0, [5]*100),
    co = ModbusSequentialDataBlock(0, [5]*100),
    hr = ModbusSequentialDataBlock(first_register, default_val), #0x9C41 40001 
    ir = ModbusSequentialDataBlock(0, [5]*100), zero_mode=True)
context = ModbusServerContext(slaves=store, single=True)

#---------------------------------------------------------------------------# 
# initialize the server information
#---------------------------------------------------------------------------# 
identity = ModbusDeviceIdentification()
identity.VendorName  = 'pymodbus'
identity.ProductCode = 'PM'
identity.VendorUrl   = 'http://github.com/andreadanzi/pymodbus/'
identity.ProductName = 'pymodbus Pump Server'
identity.ModelName   = 'pymodbus Pump Server'
identity.MajorMinorRevision = '1.0'

#---------------------------------------------------------------------------# 
# run the server you want
#---------------------------------------------------------------------------# 
time = 1 # 1 seconds delay
loop = LoopingCall(f=updating_writer, a=(context,))
loop.start(time, now=False) # initially delay by time
# set the IP address properly: change localhost with IPv4 address
StartTcpServer(context, identity=identity, address=("127.0.0.1", 502))
