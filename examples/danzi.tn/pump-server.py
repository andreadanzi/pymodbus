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
import logging.handlers
import os
import sys
import getopt
log = logging.getLogger()
log.setLevel(logging.DEBUG)
file_handler = logging.handlers.RotatingFileHandler("pump-server.log", maxBytes=5000000,backupCount=5)
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
low_p, high_p = 0, 100 # pressure (P in bar)
low_cicli, high_cicli = 1, 38
# %mw1 -> 400001
#  MODBUS data numbered N is addressed in the MODBUS PDU N-1
FIRST_REGISTER = 40001 # 40001 primo indirizzo buono (indice 0->40001)
NUM_REGISTERS = 600 # from 0 to 599 (indice 0-> reg 40001 e 599-> reg 40600)

liters_cycle = 2.42 # 230(103-50.2) - 230 corsa, 103 diam. esterno, 50.2 diam interno
default_val = [0x00]*NUM_REGISTERS
# uniform discrete random variables for pressure and flow-rate
p2_rand = randint(low_p, high_p)
cicli_rand = randint(low_cicli, high_cicli)

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
    # DA 500 A 549 DATI SCRITTI DA PLC POMPE
    default_val[0] = 12345
    default_val[1] = 1
    default_val[2] = 2
    default_val[3] = 3
    default_val[500-1] = 1 # APP_PER VERIFICA COMUNICAZIONE
    default_val[502-1] = 1 # STATO MACCHINA 1 ( IN BIT )
    default_val[503-1] = 1 # %MW503 STATO MACCHINA 2 ( IN BIT )
    default_val[504-1] = 1 # %MW504 ALLARMI MACHINA 1 ( IN BIT )
    default_val[505-1] = 1 # %MW505 ALLARMI MACHINA 2 ( IN BIT )
    default_val[506-1] = 1 # %MW506 COPIA STATO COMANDO REMOTO 1 MOMENTANEO ( bit )
    default_val[507-1] = 1 # %MW507 COPIA STATO COMANDO REMOTO 2 MOMENTANEO ( bit )
    default_val[508-1] = 1 # %MW508 COPIA STATO COMANDO REMOTO 1 CONTINUO ( bit )
    default_val[509-1] = 1 # %MW509 COPIA STATO COMANDO REMOTO 2 CONTINUO ( bit )
    default_val[512-1] = 1 # %MW512 TEMPO DI ATTIVITA' DELLA POMPA
    default_val[513-1] = 1 # %MW513 TEMPO DI ATTIVITA' DELLA POMPA INIETTORE
    default_val[514-1] = 2 # %MW514 TEMPO DI ATTIVITA' DELLA POMPA GIORNALIERO
    default_val[515-1] = 2 # %MW515 TEMPO DI ATTIVITA' DELLA INIETTORE GIORNALIERO
    default_val[516-1] = p2_rand.rvs() # %MW516 PRESSIONE ATTUALE
    default_val[517-1] = 3 # %MW517 
    default_val[518-1] = 4 # %MW518 
    default_val[519-1] = 4 # %MW519 
    cicli_min = cicli_rand.rvs()
    default_val[520-1] = cicli_min # %MW519  %MW520 CICLI / MINUTO
    q_default = cicli_min*liters_cycle
    q_m_ch = 60.0*q_default/1000.0
    # conversione float - Endian.Little il primo è il meno significativo
    builder = BinaryPayloadBuilder(endian=Endian.Little)
    builder.add_32bit_float(q_default)
    builder.add_32bit_float(q_m_ch)
    reg=builder.to_registers()
    default_val[522-1:526-1]=reg
    """
    default_val[520-1] = reg[0] # %MW520 CICLI / MINUTO
    default_val[521-1] = reg[1] # %MW521 
    default_val[522-1] = reg[2] # %MF522 LITRI / MINUTO
    default_val[523-1] = reg[3] #  
    default_val[524-1] = reg[4] # %MF524 MC / ORA
    default_val[525-1] = reg[5] #  
    """
    # DA 550 A 599 DATI LETTI DA PLC POMPE
    default_val[550-1] = 1 # %MW550 CONTATORE PER VERIFICA COMUNICAZIONE
    default_val[551-1] = 1 # %MW551 
    default_val[552-1] = 2 # %MW552 COMANDO MACCHINA DA REMOTO 1 MOMENTANEO ( bit )
    default_val[553-1] = 2 # %MW553 COMANDO MACCHINA DA REMOTO 2 MOMENTANEO ( bit )
    default_val[554-1] = 3 # %MW554 COMANDO MACCHINA DA REMOTO 1 CONTINUO ( bit )
    default_val[555-1] = 3 # %MW555 COMANDO MACCHINA DA REMOTO 2 CONTINUO ( bit )
    default_val[556-1] = 4 # %MW556 
    default_val[557-1] = 4 # %MW557 
    default_val[558-1] = 5 # %MW558 
    default_val[559-1] = 5 # %MW559 
    default_val[560-1] = 50 # %MW560 COMANDO BAR DA REMOTO
    default_val[561-1] = 6 # %MW561 
    default_val[562-1] = 32 # %MW562 COMANDO NUMERO CICLI MINUTO DA REMOTO
    default_val[600-1] = 600 # 
    log.debug("default values: " + str(default_val))
    return default_val
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
    srv_id = a[1]
    register = 3
    slave_id = 0x00
    # gets current values
    START_ADDRESS = FIRST_REGISTER-1 # inizia a leggere da 40000 e prendi gli N successivi,escluso il 40000
    values   = context[slave_id].getValues(register, START_ADDRESS, count=NUM_REGISTERS)
    # update P and Q with random values
    log.debug("pump context values: " + str(values))
    cicli_min = cicli_rand.rvs()
    values[520-1] = cicli_min # %MW520 CICLI / MINUTO
    q_val = cicli_min*liters_cycle
    q_m_ch = 60.0*q_val/1000.0
    log.debug("cicli=%d, q=%f, mc=%f" % (cicli_min, q_val,q_m_ch))
    # conversione float - Endian.Little il primo è il meno significativo
    builder = BinaryPayloadBuilder(endian=Endian.Little)
    builder.add_32bit_float(q_val)
    builder.add_32bit_float(q_m_ch)
    reg=builder.to_registers()
    log.debug("2 x 32bit_float = %s" % str(reg))
    values[522-1:526-1]=reg
    
    """
    values[22] = q_val # %MF522 LITRI / MINUTO
    values[24] = q_m_ch # %MF524 MC / ORA
    """
    p_new = p2_rand.rvs()
    log.debug("p_new=%d" % p_new)
    values[516-1] = p_new # %MW516 PRESSIONE ATTUALE
    if values[516-1] > values[560-1]:
        values[516-1] = values[560-1]
    log.debug("On Pump Server %02d new values: %s" % (srv_id, str(values[516-1:526-1])))
    # assign new values to context
    values[600-1] = 699
    context[slave_id].setValues(register, START_ADDRESS, values)

def context_factory():
    default_val = default_val_factory()
    #---------------------------------------------------------------------------# 
    # initialize your data store
    #---------------------------------------------------------------------------# 
    store = ModbusSlaveContext(
        di = ModbusSequentialDataBlock(0, [5]*100),
        co = ModbusSequentialDataBlock(0, [5]*100),
        hr = ModbusSequentialDataBlock(FIRST_REGISTER, default_val), #0x9C41 40001 
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
    identity.ProductName = 'pymodbus Pump Server'
    identity.ModelName   = 'pymodbus Pump Server'
    identity.MajorMinorRevision = '1.0'

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