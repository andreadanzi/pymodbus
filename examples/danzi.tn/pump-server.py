# -*- coding: utf-8 -*-
#!/usr/bin/env python
'''
python pump-server.py -p 5320 -n 1
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

class ModbusMySequentialDataBlock(ModbusSequentialDataBlock):

    def setValues(self, address, values):
        ''' Sets the requested values of the datastore

        :param address: The starting address
        :param values: The new values to be set
        '''
        if not isinstance(values, list):
            values = [values]
        start = address - self.address
        self.values[start:start + len(values)] = values
        if start <= 550 < start + len(values):
            if self.values[500] != values[550-start]:
                log.debug("ModbusMySequentialDataBlock.setValues updating 500({0}) with new value {1}".format(self.values[500],values[550-start]))
                self.values[500] = values[550-start]


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
import math
low_p, high_p = 0, 100 # pressure (P in bar)
low_cicli, high_cicli = 1, 38
# %mw1 -> 400001
#  MODBUS data numbered N is addressed in the MODBUS PDU N-1
FIRST_REGISTER = 0 # danzi.tn@20160729 primo indirizzo buono (iniziano da 0, ma noi leggiamo da 500 a 599)
NUM_REGISTERS = 600 # from 0 to 599 (indice 0-> reg 40001 e 599-> reg 40600)

liters_cycle = 2.42 # 230(103-50.2) - 230 corsa, 103 diam. esterno, 50.2 diam interno
default_val = [0x00]*NUM_REGISTERS
# uniform discrete random variables for pressure and flow-rate
p2_rand = randint(low_p, high_p)
cicli_rand = randint(low_cicli, high_cicli)
delta_rand = randint(-2, 2)

def out_val_p(x,top):
    x = float(x)/60. # ragioniamo in secondi
    xx = (x-1.)/2.
    y = 1+xx/math.sqrt(1.+xx**2)
    yy = y/2
    return yy*top

def out_val_q(x,top):
    x = float(x)/60. # ragioniamo in secondi
    xx = (1.-x)/2.
    y = 1+xx/math.sqrt(1.+xx**2)
    yy = y/2
    return yy*top


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

    # DA 500 A 549 DATI SCRITTI DA PLC POMPE
    default_val[0] = 12345
    default_val[1] = 1
    default_val[2] = 2
    default_val[3] = 3
    # qui inizia
    default_val[500] = 1 # APP_PER VERIFICA COMUNICAZIONE
    as_bits_502 = [0]*16
    as_bits_502[0] = 1
    as_bits_502[6] = 1
    as_bits_502[10] = 1
    builder = BinaryPayloadBuilder(endian=Endian.Little)
    builder.add_bits(as_bits_502)
    reg=builder.to_registers()
    print " STATO MACCHINA 1 ( IN BIT ) %d" % reg[0]
    default_val[502] = reg[0] # STATO MACCHINA 1 ( IN BIT )
    default_val[503] = 0 # %MW503 STATO MACCHINA 2 ( IN BIT )
    default_val[504] = 0 # %MW504 ALLARMI MACHINA 1 ( IN BIT )
    default_val[505] = 0 # %MW505 ALLARMI MACHINA 2 ( IN BIT )
    default_val[506] = 0 # %MW506 COPIA STATO COMANDO REMOTO 1 MOMENTANEO ( bit )
    default_val[507] = 1 # %MW507 COPIA STATO COMANDO REMOTO 2 MOMENTANEO ( bit )
    default_val[508] = 1 # %MW508 COPIA STATO COMANDO REMOTO 1 CONTINUO ( bit )
    default_val[509] = 1 # %MW509 COPIA STATO COMANDO REMOTO 2 CONTINUO ( bit )
    default_val[512] = 1 # %MW512 TEMPO DI ATTIVITA' DELLA POMPA
    default_val[513] = 1 # %MW513 TEMPO DI ATTIVITA' DELLA POMPA INIETTORE
    default_val[514] = 2 # %MW514 TEMPO DI ATTIVITA' DELLA POMPA GIORNALIERO
    default_val[515] = 2 # %MW515 TEMPO DI ATTIVITA' DELLA INIETTORE GIORNALIERO
    default_val[516] = 1 # %MW516 PRESSIONE ATTUALE
    default_val[517] = 3 # %MW517
    default_val[518] = 4 # %MW518
    default_val[519] = 4 # %MW519
    cicli_min = 29
    default_val[520] = cicli_min # %MW519  %MW520 CICLI / MINUTO
    q_default = cicli_min*liters_cycle
    q_m_ch = 60.0*q_default/1000.0
    # conversione float - Endian.Little il primo è il meno significativo
    builder = BinaryPayloadBuilder(endian=Endian.Little)
    builder.add_32bit_float(q_default)
    builder.add_32bit_float(q_m_ch)
    reg=builder.to_registers()
    default_val[522:526]=reg
    """
    default_val[520] = reg[0] # %MW520 CICLI / MINUTO
    default_val[521] = reg[1] # %MW521
    default_val[522] = reg[2] # %MF522 LITRI / MINUTO
    default_val[523] = reg[3] #
    default_val[524] = reg[4] # %MF524 MC / ORA
    default_val[525] = reg[5] #
    """
    # DA 550 A 599 DATI LETTI DA PLC POMPE
    default_val[550] = 1 # %MW550 CONTATORE PER VERIFICA COMUNICAZIONE
    default_val[551] = 1 # %MW551
    default_val[552] = 0 # %MW552 COMANDO MACCHINA DA REMOTO 1 MOMENTANEO ( bit )
    default_val[553] = 2 # %MW553 COMANDO MACCHINA DA REMOTO 2 MOMENTANEO ( bit )
    default_val[554] = 3 # %MW554 COMANDO MACCHINA DA REMOTO 1 CONTINUO ( bit )
    default_val[555] = 3 # %MW555 COMANDO MACCHINA DA REMOTO 2 CONTINUO ( bit )
    default_val[556] = 4 # %MW556
    default_val[557] = 4 # %MW557
    default_val[558] = 5 # %MW558
    default_val[559] = 5 # %MW559
    default_val[560] = 35 # %MW560 COMANDO BAR DA REMOTO
    default_val[561] = 6 # %MW561
    default_val[562] = 35 # %MW562 COMANDO NUMERO CICLI MINUTO DA REMOTO
    default_val[599] = 600 #
    log.debug("default values: " + str(default_val))
    return default_val
#---------------------------------------------------------------------------#
# define your callback process
#---------------------------------------------------------------------------#
g_Time = 0
def updating_writer(a):
    ''' A worker process that runs every so often and
    updates live values of the context. It should be noted
    that there is a race condition for the update.

    :param arguments: The input arguments to the call
    '''
    global g_Time
    if g_Time >= 60*4:
        g_Time = 0
        log.debug("g_Time reset")
        print "g_Time reset"
    g_Time += 1
    
    log.debug("updating the context at {0}".format(g_Time))
    context  = a[0]
    srv_id = a[1]
    register = 3
    slave_id = 0x00
    # gets current values
    if context[slave_id].zero_mode:
        START_ADDRESS = FIRST_REGISTER   # if zero_mode=True
    else:
        START_ADDRESS = FIRST_REGISTER-1 # if zero_mode=False. inizia a leggere da 40000 e prendi gli N successivi,escluso il 40000
    values   = context[slave_id].getValues(register, START_ADDRESS, count=NUM_REGISTERS)
    # update P and Q with random values
    log.debug("pump context values: " + str(values))
    #cicli_min = cicli_rand.rvs()
    cicli_min = int(out_val_q(g_Time,50.))

    """
    values[22] = q_val # %MF522 LITRI / MINUTO
    values[24] = q_m_ch # %MF524 MC / ORA
    """
    p_new = int(out_val_p(g_Time,40.)) + delta_rand.rvs() 
    log.debug("p_new=%d" % p_new)
    values[516] = p_new # %MW516 PRESSIONE ATTUALE
    ##########################################
    ### Verifica limite massimo P
    #############################
    if values[516] > values[560]:
        log.debug("PMax exceeded: %d (516) > %d (560)" % (values[516],values[560]) )
        cicli_min = values[560]
        values[516] = values[560]
        # %MW560 CICLI / MINUTO
    ##########################################
    ### Verifica limite massimo Q
    #############################
    if cicli_min > values[562]:
        log.debug("QMax exceeded: %d (520) > %d (562)" % (cicli_min,values[562]) )
        cicli_min = values[562]
    # %MW520 CICLI / MINUTO
    values[520] = cicli_min
    q_val = cicli_min*liters_cycle
    q_m_ch = 60.0*q_val/1000.0
    log.debug("cicli=%d, q=%f, mc=%f" % (cicli_min, q_val,q_m_ch))
    # conversione float - Endian.Little il primo è il meno significativo
    builder = BinaryPayloadBuilder(endian=Endian.Little)
    builder.add_32bit_float(q_val)
    builder.add_32bit_float(q_m_ch)
    reg=builder.to_registers()
    log.debug("2 x 32bit_float = %s" % str(reg))
    values[522:526]=reg

    log.debug("On Pump Server %02d new values (516-525): %s" % (srv_id, str(values[516:526])))
    decoder = BinaryPayloadDecoder.fromRegisters(values[502:503],endian=Endian.Little)
    bits_502 = decoder.decode_bits()
    bits_502 += decoder.decode_bits()
    decoder = BinaryPayloadDecoder.fromRegisters(values[552:553],endian=Endian.Little)
    bits_552 = decoder.decode_bits()
    bits_552 += decoder.decode_bits()
    decoder = BinaryPayloadDecoder.fromRegisters(values[506:507],endian=Endian.Little)
    bits_506 = decoder.decode_bits()
    bits_506 += decoder.decode_bits()
    if bits_552[2]:
        print "start iniettore da remoto"
        log.debug("start iniettore da remoto")
        bits_502[7] = 1 # START INIETTORE
        bits_506[2] = 1
        bits_506[3] = 0
        bits_552[2] = 0
        bits_builder = BinaryPayloadBuilder(endian=Endian.Little)
        bits_builder.add_bits(bits_502)
        bits_builder.add_bits(bits_506)
        bits_builder.add_bits(bits_552)
        bits_reg = bits_builder.to_registers()
        values[502:503]=[bits_reg[0]]
        values[506:507]=[bits_reg[1]]
        values[552:553]=[bits_reg[2]]
    if bits_552[3]:
        print "stop iniettore da remoto"
        log.debug("stop iniettore da remoto")
        bits_502[7] = 0 # STOP INIETTORE
        bits_506[2] = 0
        bits_506[3] = 1
        bits_552[3] = 0
        bits_builder = BinaryPayloadBuilder(endian=Endian.Little)
        bits_builder.add_bits(bits_502)
        bits_builder.add_bits(bits_506)
        bits_builder.add_bits(bits_552)
        bits_reg=bits_builder.to_registers()
        values[502:503]=[bits_reg[0]]
        values[506:507]=[bits_reg[1]]
        values[552:553]=[bits_reg[2]]
    # assign new values to context
    values[599] = 699
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
        hr = ModbusMySequentialDataBlock(FIRST_REGISTER, default_val), #0x9C41 40001
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
