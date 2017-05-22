# -*- coding: utf-8 -*-
"""
Created on Thu Aug 11 11:40:06 2016

@author: andrea
"""

import gi
import csv
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from collections import deque
from pymodbus.server.async import ModbusServerFactory
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder
import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId

from twisted.internet.task import LoopingCall

from twisted.internet import gtk3reactor
gtk3reactor.install()

from twisted.internet import reactor

import logging, datetime, os, ConfigParser
import collections
import logging.handlers

from matplotlib.figure import Figure
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas

from scipy.stats import randint
import numpy as np

liters_cycle = 2.42 # 230(103-50.2) - 230 corsa, 103 diam. esterno, 50.2 diam interno
low, high = 4000, 20000 # danzi.tn@20160728 current as nanoampere nA - analogic values
low_p, high_p = 0, 1000 # danzi.tn@20160728 pressure range (P in bar/10)
low_q, high_q = 0, 2000 # danzi.tn@20160728 flow-rate range (Q in lit/min/10)
#  MODBUS data numbered N is addressed in the MODBUS PDU N-1

# uniform discrete random variables for simulating pressure and flow-rate
p_rand = randint(low, high) # pressure
q_rand = randint(low, 8000) # flow rate
delta_rand = randint(-100, 100)


# Least squares polynomial (linear) fit.
#   Conversion from current (mA) to pressure (bar)
p_fit = np.polyfit([low, high],[low_p, high_p],1)
p_func = np.poly1d(p_fit)
#   Conversion from current (mA) to flow-rate (lit/min)
q_fit = np.polyfit([low, high],[low_q, high_q],1)
q_func = np.poly1d(q_fit)


sCurrentWorkingdir = os.getcwd()
sDate = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
export_csv = "bgu_simulator_{0}.csv".format(sDate)
export_csv_path = os.path.join(sCurrentWorkingdir,export_csv)

sCFGName = 'bgu_simulator.cfg'
smtConfig = ConfigParser.RawConfigParser()
cfgItems = smtConfig.read(sCFGName)

log = logging.getLogger("csv")
log.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(export_csv_path, maxBytes=5000000,backupCount=5)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s;%(message)s')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)
log.info("p_mA1;p_Eng1;q_mA1;q_Eng1;p_max;q_max")
test_reg_no = 0 # test the expected value (Machine ID, defaukt is 0x5100)
test_value = smtConfig.getint('Manifold_1', 'id') # 0x5200 => 20992
# test_value = 20736 # per quell'altro modulo si usa 0x5100 => 20736

logInfo = logging.getLogger("info")
logInfo.setLevel(logging.DEBUG)


fileInfo_handler = logging.handlers.RotatingFileHandler("{0}.log".format(os.path.basename(__file__).split(".")[0]), maxBytes=5000000,backupCount=5)
fileInfo_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
fileInfo_handler.setFormatter(formatter)
logInfo.addHandler(fileInfo_handler)

# CAVALLETTO 1
manifold_host_1 = '127.0.0.1' # 10.243.37.xx
manifold_port_1 = "5020"  # 502
client_1 = None


low, high = 4000, 20000 # danzi.tn@20160728 current as nanoampere nA - analogic values

low_2, high_2 = 0, 20000 # danzi.tn@20170314

# Scale P 
low_p, high_p = 0, 1000 # danzi.tn@20160728 pressure range (P in bar/10)
# Scale Q
low_q, high_q = 0, 2000 # danzi.tn@20160728 flow-rate range (Q in lit/min/10)

low_q2, high_q2 = -50, 2000 # danzi.tn@20160728 flow-rate range (Q in lit/min/10)

# Least squares polynomial (linear) fit.
#   Conversion from current (mA) to pressure (bar)
p_fit = np.polyfit([low, high],[low_p, high_p],1)
pEngFunc = np.poly1d(p_fit)
#   Conversion from current (mA) to flow-rate (lit/min)
q_fit = np.polyfit([low, high],[low_q, high_q],1)
qEngFunc = np.poly1d(q_fit)




def phdlf( q ,pipe_length, hdlf ):
    p_hdlf = hdlf[0]*q**2+hdlf[1]*q+hdlf[0]
    p_hdlf = p_hdlf*pipe_length
    return p_hdlf




stdDev = 0.1

litCiclo = 2.464

listP1 = []

cicli_volt = {0:0,
                1:1800,
                2:2100,
                3:2350,
                4:2590,
                5:2820,
                6:3100,
                7:3250,
                8:3350,
                9:3600,
                10:3800,
                11:3900,
                12:4000,
                13:4150,
                14:4300,
                15:4450,
                16:4600,
                17:4750,
                18:4850,
                19:4950,
                20:5100,
                21:5250,
                22:5400,
                23:5550,
                24:5700,
                25:5850,
                26:5950,
                27:6050,
                28:6150,
                29:6300,
                30:6400,
                31:6550,
                32:6700,
                33:6850,
                34:7150,
                35:7150,
                36:7150,
                37:7150
              }


def default_pump_val_factory():
    default_val = [0x00]*600
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
    default_val[560] = 0 # %MW560 COMANDO BAR DA REMOTO
    default_val[561] = 6 # %MW561
    default_val[562] = 0 # %MW562 COMANDO NUMERO CICLI MINUTO DA REMOTO
    default_val[599] = 600 #
    logInfo.debug("default values: " + str(default_val))
    return default_val


def default_man_val_factory():
    default_val = []
    
    local_ip_address = "127.0.0.1"
    print(local_ip_address)  # prints 10.0.2.40
    local_ip_address_splitted = local_ip_address.split(".")
    default_val = [0x00]*120
    # Default pressure as mA  
    # default_val[0] = 0x5100 # => 20736
    default_val[0] = smtConfig.getint('Manifold_1', 'id') # danzi.tn@20160728 valore fisso per tutti i cavalletti pari a 20992  
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
    logInfo.debug("default values: " + str(default_val))
    return default_val

class ModbusMySequentialDataBlock(ModbusSequentialDataBlock):

    def set_handler(self, hndlr):
        self.hndlr = hndlr
    
        
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
                logInfo.debug("ModbusMySequentialDataBlock.setValues updating 500({0}) with new value {1}".format(self.values[500],values[550-start]))
                self.values[500] = values[550-start]
        if start <= 552 < start + len(values):
            global g_Time
            global s_Time
            decoder = BinaryPayloadDecoder.fromRegisters(self.values[502:503],endian=Endian.Little)
            bits_502 = decoder.decode_bits()
            bits_502 += decoder.decode_bits()
            decoder = BinaryPayloadDecoder.fromRegisters(self.values[506:507],endian=Endian.Little)
            bits_506 = decoder.decode_bits()
            bits_506 += decoder.decode_bits()
            decoder = BinaryPayloadDecoder.fromRegisters(values[552-start:553-start],endian=Endian.Little)
            bits_552 = decoder.decode_bits()
            bits_552 += decoder.decode_bits()
            logInfo.debug("ModbusMySequentialDataBlock.setValues updating 552({0}) {1}".format(values[552-start], bits_552))
            if bits_552[2]:
                print "ModbusMySequentialDataBlock.setValues start iniettore da remoto"
                logInfo.debug("ModbusMySequentialDataBlock.setValues start iniettore da remoto")
                g_Time = 0
                bits_502[7] = 1 # START INIETTORE
                self.hndlr.pumpStarted = True
                bits_506[2] = 1
                bits_506[3] = 0
                bits_552[2] = 0
                bits_builder = BinaryPayloadBuilder(endian=Endian.Little)
                bits_builder.add_bits(bits_502)
                bits_builder.add_bits(bits_506)
                bits_builder.add_bits(bits_552)
                bits_reg = bits_builder.to_registers()
                self.values[502:503]=[bits_reg[0]]
                self.values[506:507]=[bits_reg[1]]
                self.values[552:553]=[bits_reg[2]]
            if bits_552[3]:
                print "ModbusMySequentialDataBlock.setValues stop iniettore da remoto"
                logInfo.debug("ModbusMySequentialDataBlock.setValues stop iniettore da remoto")
                bits_502[7] = 0 # STOP INIETTORE
                bits_506[2] = 0
                self.hndlr.pumpStarted = False
                bits_506[3] = 1
                bits_552[3] = 0
                bits_builder = BinaryPayloadBuilder(endian=Endian.Little)
                bits_builder.add_bits(bits_502)
                bits_builder.add_bits(bits_506)
                bits_builder.add_bits(bits_552)
                bits_reg=bits_builder.to_registers()
                self.values[502:503]=[bits_reg[0]]
                self.values[506:507]=[bits_reg[1]]
                self.values[552:553]=[bits_reg[2]]

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
    for iter, address  in enumerate(address_list):
        address = address or ("", Defaults.Port)
        context = context_list[iter]
        identity = identity_list[iter]
        framer  = ModbusSocketFramer
        factory = ModbusServerFactory(context, framer, identity, **kwargs)
        if console:
            from pymodbus.internal.ptwisted import InstallManagementConsole
            InstallManagementConsole({'factory': factory})

        logInfo.info("Starting Modbus TCP Server on %s:%s" % address)
        reactor.listenTCP(address[1], factory, interface=address[0])


def updating_pump_writer(a):
    ''' A worker process that runs every so often and
    updates live values of the context. It should be noted
    that there is a race condition for the update.

    :param arguments: The input arguments to the call
    '''
    context  = a[0]
    srv_id = a[1]
    handler = a[2]
    register = 3
    slave_id = 0x00
   
    values   = context[slave_id].getValues(register, 0, count=600)
    # update P and Q with random values
    logInfo.debug("PUMP context values: " + str(values))

    logInfo.debug("PUMP p_out=%d; q_out=%d" % (handler.p_out,handler.q_out))

    decoder = BinaryPayloadDecoder.fromRegisters(values[502:503],endian=Endian.Little)
    bits_502 = decoder.decode_bits()
    bits_502 += decoder.decode_bits()
    decoder = BinaryPayloadDecoder.fromRegisters(values[552:553],endian=Endian.Little)
    bits_552 = decoder.decode_bits()
    bits_552 += decoder.decode_bits()
    decoder = BinaryPayloadDecoder.fromRegisters(values[506:507],endian=Endian.Little)
    bits_506 = decoder.decode_bits()
    bits_506 += decoder.decode_bits()

    cicli_min = 0
    p_new = 0
    q_val = 0
    # if iniettore Started
    if handler.pumpStarted and not bits_502[7]:    
        handler.pumpStarted = False
    
    if bits_502[7]:
        #cicli_min = cicli_rand.rvs()
        q_val = handler.q_out
        if q_val < 0:
            q_val = 0
        cicli_min = int(q_val / liters_cycle )
        p_new = handler.p_out
        handler.lblPumpStatus.set_label("Pump ON")
    else:
        handler.lblPumpStatus.set_label("Pump OFF")
   

    logInfo.debug("PUMP p_new=%d" % p_new)
    
    q_m_ch = 60.0*q_val/1000.0
    handler.cicli_min = cicli_min
    handler.q_m_ch = q_m_ch
    logInfo.debug("PUMP cicli=%d, q=%f, mc=%f" % (cicli_min, q_val,q_m_ch))
    # conversione float - Endian.Little il primo è il meno significativo
    handler.p_pump_out = p_new
    handler.q_pump_out = cicli_min
    values[516] = p_new # %MW516 PRESSIONE ATTUALE
    values[520] = cicli_min
    
    handler.qmax = values[562]
    handler.pmax = values[560]
    builder = BinaryPayloadBuilder(endian=Endian.Little)
    builder.add_32bit_float(q_val)
    builder.add_32bit_float(q_m_ch)
    reg=builder.to_registers()
    logInfo.debug("PUMP 2 x 32bit_float = %s" % str(reg))
    values[522:526]=reg

    logInfo.debug("PUMP On Pump Server %02d new values (516-525): %s" % (srv_id, str(values[516:526])))

    # assign new values to context
    values[599] = 699
    context[slave_id].setValues(register, 0, values)



def updating_man_writer(a):
    ''' A worker process that runs every so often and
    updates live values of the context.

    :param arguments: The input arguments to the call
    '''
    context  = a[0]
    srv_id = a[1]
    handler = a[2]

    
    register = 3 # holding registers
    slave_id = 0x00
    values   = context[slave_id].getValues(register, 0, count=120)
    logInfo.debug("p_out=%d; q_out=%d" % (handler.p_out,handler.q_out))
    q_out = handler.q_out
    q_sign = 0
    if q_out < 0:
        q_sign = 1
        q_out = abs(q_out)
    
    p_new = int((10.*handler.p_out - p_fit[1])/p_fit[0])
    q_new = int((10.*q_out - q_fit[1])/q_fit[0])
    
    logInfo.debug("p_new=%d; q_new=%d" % (p_new,q_new))
    values[4-1] = p_new
    handler.p_AnOut = p_new
    values[5-1] = int(p_func(p_new)) # as bar
    values[6-1] = q_new # as mA
    handler.q_AnOut = q_new
    
    values[7-1] = abs(int(q_func(q_new))) # as lit/min
    values[12-1] = q_sign # as lit/min
    values[120-1] = 999
    logInfo.debug("On cavalletto server %02d new values: %s" %(srv_id, str(values)))
    # assign new values to context
    context[slave_id].setValues(register, 0, values)

def context_pump_factory(hndlr):
    default_val = default_pump_val_factory()
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
    mmsdb = ModbusMySequentialDataBlock(0, default_val)
    mmsdb.set_handler(hndlr)
    store = ModbusSlaveContext(
        di = ModbusSequentialDataBlock(0, [5]*100),
        co = ModbusSequentialDataBlock(0, [5]*100),
        hr = mmsdb, #0x9C41 40001
        ir = ModbusSequentialDataBlock(0, [5]*100),zero_mode=True)
    context = ModbusServerContext(slaves=store, single=True)
    return context

def context_man_factory():
    default_val = default_man_val_factory()
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
        hr = ModbusSequentialDataBlock(0, default_val), #only holding registers starting from 40001
        ir = ModbusSequentialDataBlock(0, [5]*100),zero_mode=True)
    context = ModbusServerContext(slaves=store, single=True)
    return context

#---------------------------------------------------------------------------#
# initialize the server information
#---------------------------------------------------------------------------#
def identity_factory(sType):
    identity = ModbusDeviceIdentification()
    identity.VendorName  = 'pymodbus'
    identity.ProductCode = 'PM'
    identity.VendorUrl   = 'http://github.com/andreadanzi/pymodbus/'
    identity.ProductName = 'pymodbus {0} Server'.format(sType)
    identity.ModelName   = 'pymodbus {0} Server'.format(sType)
    identity.MajorMinorRevision = '1.0'

    
def getVoltsFromFlowRate(f):
    y=82.28
    if f<=1800:
        y=f*0.00134444444444+1.57009245868e-16
    elif f<=2100:
        y=f*0.00806666666667+-12.1
    elif f<=2350:
        y=f*0.00968+-15.488
    elif f<=2590:
        y=f*0.0100833333333+-16.4358333333
    elif f<=2820:
        y=f*0.0105217391304+-17.5713043478
    elif f<=3100:
        y=f*0.00864285714286+-12.2728571429
    elif f<=3250:
        y=f*0.0161333333333+-35.4933333333
    elif f<=3350:
        y=f*0.0242+-61.71
    elif f<=3600:
        y=f*0.00968+-13.068
    elif f<=3800:
        y=f*0.0121+-21.78
    elif f<=3900:
        y=f*0.0242+-67.76
    elif f<=4000:
        y=f*0.0242+-67.76
    elif f<=4150:
        y=f*0.0161333333333+-35.4933333333
    elif f<=4300:
        y=f*0.0161333333333+-35.4933333333
    elif f<=4450:
        y=f*0.0161333333333+-35.4933333333
    elif f<=4600:
        y=f*0.0161333333333+-35.4933333333
    elif f<=4750:
        y=f*0.0161333333333+-35.4933333333
    elif f<=4850:
        y=f*0.0242+-73.81
    elif f<=4950:
        y=f*0.0242+-73.81
    elif f<=5100:
        y=f*0.0161333333333+-33.88
    elif f<=5250:
        y=f*0.0161333333333+-33.88
    elif f<=5400:
        y=f*0.0161333333333+-33.88
    elif f<=5550:
        y=f*0.0161333333333+-33.88
    elif f<=5700:
        y=f*0.0161333333333+-33.88
    elif f<=5850:
        y=f*0.0161333333333+-33.88
    elif f<=5950:
        y=f*0.0242+-81.07
    elif f<=6050:
        y=f*0.0242+-81.07
    elif f<=6150:
        y=f*0.0242+-81.07
    elif f<=6300:
        y=f*0.0161333333333+-31.46
    elif f<=6400:
        y=f*0.0242+-82.28
    elif f<=6550:
        y=f*0.0161333333333+-30.6533333333
    elif f<=6700:
        y=f*0.0161333333333+-30.6533333333
    elif f<=6850:
        y=f*0.0161333333333+-30.6533333333
    elif f<=7150:
        y=f*0.00806666666667+24.6033333333
    else:
        y=82.28
    return int(y)




def getFlowRateAsVolts(f):
    y = 7150
    if f<=2.42:
        y=f*743.801652893+0.0
    elif f<=4.84:
        y=f*123.966942149+1500.0
    elif f<=7.26:
        y=f*103.305785124+1600.0
    elif f<=9.68:
        y=f*99.173553719+1630.0
    elif f<=12.1:
        y=f*95.041322314+1670.0
    elif f<=14.52:
        y=f*115.702479339+1420.0
    elif f<=16.94:
        y=f*61.9834710744+2200.0
    elif f<=19.36:
        y=f*41.3223140496+2550.0
    elif f<=21.78:
        y=f*103.305785124+1350.0
    elif f<=24.2:
        y=f*82.6446280992+1800.0
    elif f<=26.62:
        y=f*41.3223140496+2800.0
    elif f<=29.04:
        y=f*41.3223140496+2800.0
    elif f<=31.46:
        y=f*61.9834710744+2200.0
    elif f<=33.88:
        y=f*61.9834710744+2200.0
    elif f<=36.3:
        y=f*61.9834710744+2200.0
    elif f<=38.72:
        y=f*61.9834710744+2200.0
    elif f<=41.14:
        y=f*61.9834710744+2200.0
    elif f<=43.56:
        y=f*41.3223140496+3050.0
    elif f<=45.98:
        y=f*41.3223140496+3050.0
    elif f<=48.4:
        y=f*61.9834710744+2100.0
    elif f<=50.82:
        y=f*61.9834710744+2100.0
    elif f<=53.24:
        y=f*61.9834710744+2100.0
    elif f<=55.66:
        y=f*61.9834710744+2100.0
    elif f<=58.08:
        y=f*61.9834710744+2100.0
    elif f<=60.5:
        y=f*61.9834710744+2100.0
    elif f<=62.92:
        y=f*41.3223140496+3350.0
    elif f<=65.34:
        y=f*41.3223140496+3350.0
    elif f<=67.76:
        y=f*41.3223140496+3350.0
    elif f<=70.18:
        y=f*61.9834710744+1950.0
    elif f<=72.6:
        y=f*41.3223140496+3400.0
    elif f<=75.02:
        y=f*61.9834710744+1900.0
    elif f<=77.44:
        y=f*61.9834710744+1900.0
    elif f<=79.86:
        y=f*61.9834710744+1900.0
    elif f<=82.28:
        y=f*123.966942149+-3050.0
    else:
        y = 7150
    return int(y)

builder = Gtk.Builder()
builder.add_from_file("bgu_simulator.glade")


scrolledwindow1 = builder.get_object("scrolledwindow1")

switchPumpStatus = builder.get_object("switchPumpStatus")

x_size = 90
f = Figure(figsize=(16, 9), dpi=100)
a = f.add_subplot(111)
for tick in a.xaxis.get_major_ticks():
    tick.label.set_fontsize(10)
for tick in a.yaxis.get_major_ticks():
    tick.label.set_fontsize(10)
a.grid(True)
a.set_xlabel('Time', fontsize=10)
a.set_ylim(-10, 80)
a.set_xlim(0, x_size)
a2 = a.twinx()

a2.set_ylim(-10, 80)
for tick in a2.yaxis.get_major_ticks():
    tick.label.set_fontsize(10)

a2.set_ylabel('Flow rate (Q lit/min)', fontsize=10)


a.set_ylabel('Pressure (P bar)', fontsize=10)


scrolledwindow1.set_border_width(5)

canvas = FigureCanvas(f)  # a Gtk.DrawingArea
canvas.set_size_request(800, 450)
scrolledwindow1.add_with_viewport(canvas)
canvas.show()

designR = 25
designQmin = 1
designRTW = 2

if len(cfgItems) > 0:
    mongo_host = smtConfig.get('Mongodb', 'host')
    mongo_port = smtConfig.getint('Mongodb', 'port')    
    mongo_db = smtConfig.get('Mongodb', 'db')       
    str_mongo_stages = smtConfig.get('Mongodb', 'stages') 
    mongo_stages_array = str_mongo_stages.split(",")
    mongo_stages = []
    for st in mongo_stages_array:
        mongo_stages.append(ObjectId(st))
    
    if smtConfig.has_option('Manifold_1', 'host') and smtConfig.has_option('Manifold_1', 'port'):
        manifold_host_1 = smtConfig.get('Manifold_1', 'host')
        manifold_port_1 = smtConfig.get('Manifold_1', 'port')
    if smtConfig.has_option('Manifold_2', 'host') and smtConfig.has_option('Manifold_2', 'port'):
        manifold_host_2 = smtConfig.get('Manifold_2', 'host')
        manifold_port_2 = smtConfig.get('Manifold_2', 'port')

    if smtConfig.has_option('Pump', 'host') and smtConfig.has_option('Pump', 'port'):
        pump_host = smtConfig.get('Pump', 'host')
        pump_port = smtConfig.get('Pump', 'port')
    
    if smtConfig.has_section('Design'):
        designR = smtConfig.getint('Design', 'R')
        designQmin = smtConfig.getint('Design', 'Qmin')
        designRTW = smtConfig.getint('Design', 'RTW')


    builder.get_object("txtIP1").set_text(manifold_host_1)
    builder.get_object("txtPort1").set_text(manifold_port_1)
    builder.get_object("txtPortPump").set_text(pump_port)
    builder.get_object("txtIPPump").set_text(pump_host)
    



reg_descr = {"%MW502:X0":"Pompa in locale",
             "%MW502:X1":"Pompa in remoto",
             "%MW502:X2":"ND",
             "%MW502:X3":"ND",
             "%MW502:X4":"Pompa in allarme",
             "%MW502:X5":"ND",
             "%MW502:X6":"Pompa olio on",
             "%MW502:X7":"Iniettore in ciclo on",
             "%MW502:X8":"ND",
             "%MW502:X9":"ND",
             "%MW502:X10":"Macchina pronta per comando remoto",
             "%MW502:X11":"ND",
             "%MW502:X12":"ND",
             "%MW502:X13":"ND",
             "%MW502:X14":"All_Connessione_1 Errato?",
             "%MW502:X15":"All_Connessione_2 Errato?",
             "%MW504:X0":"All_Max_Pressione",
             "%MW504:X1":"All_Emergenza",
             "%MW504:X2":"All_TermicoPompa",
             "%MW504:X3":"All_TermicoScambiatore1",
             "%MW504:X4":"All_LivelloOlio",
             "%MW504:X5":"All_Pressostato",
             "%MW504:X6":"All_Configurazione PLC",
             "%MW504:X7":"All_Batteria",
             "%MW504:X8":"All_termicoScambiatore2",
             "%MW504:X9":"All_TermicoPompaRicircolo",
             "%MW504:X10":"All_TemperaturaVasca",
             "%MW504:X11":"ND",
             "%MW504:X12":"ND",
             "%MW504:X13":"All_Vasca_vuota",
             "%MW504:X14":"All_Connessione_Rete",
             "%MW504:X15":"All_Mancata_Parita",
             "%MW506:X0":"START POMPA REMOTO PLC",
             "%MW506:X1":"STOP POMPA REMOTO PLC",
             "%MW506:X2":"START INIET. REMOTO PLC",
             "%MW506:X3":"STOP INIET. REMOTO PLC",
             "%MW506:X4":"ND",
             "%MW506:X5":"ND",
             "%MW506:X6":"ND",
             "%MW506:X7":"ND",
             "%MW506:X8":"ND",
             "%MW506:X9":"ND",
             "%MW506:X10":"Copia Ciclo di comando in corso",
             "%MW506:X11":"ND",
             "%MW506:X12":"Copia Alzo per Analogico Pompa",
             "%MW506:X13":"ND",
             "%MW506:X14":"RESET TOTALIZ. GIORNALIERI PLC",
             "%MW506:X15":"RESET TOTALIZ. PERPETUI PLC",
             "%MW512": "TEMPO DI ATTIVITA' POMPA",
             "%MW513": "TEMPO DI ATTIVITA' INIETTORE",
             "%MW514": "TEMPO DI ATTIVITA' POMPA GIORNALIERO",
             "%MW515": "TEMPO DI ATTIVITA' INIETTORE GIORNALIERO",
             "%MW516": "PRESSIONE ATTUALE (BAR)",
             "%MW520": "PORTATA ATTUALE (CICLI/MIN)",
             "%MW500": "COUNTER PLC",
             "%MW550": "COUNTER REMOTO",
             "%MW560": "COMANDO PRESSIONE MAX REMOTO (BAR)",
             "%MW562": "COMANDO PORTATA MAX REMOTO (CICLI/MIN)",
             "%MW564": "Valore Analogico Pompa 0-10000",
             "%MW552:X0":"START POMPA REMOTO",
             "%MW552:X1":"STOP POMPA REMOTO",
             "%MW552:X2":"START INIET. REMOTO",
             "%MW552:X3":"STOP INIET. REMOTO",
             "%MW552:X4":"ND",
             "%MW552:X5":"ND",
             "%MW552:X6":"ND",
             "%MW552:X7":"ND",
             "%MW552:X8":"ND",
             "%MW552:X9":"ND",
             "%MW552:X10":"Ciclo di comando in corso",
             "%MW552:X11":"ND",
             "%MW552:X12":"Alzo per Analogico Pompa",
             "%MW552:X13":"ND",
             "%MW552:X14":"RESET TOTALIZ. GIORNALIERI REMOTO",
             "%MW552:X15":"RESET TOTALIZ. PERPETUI REMOTO"}




class Handler(object):
    def __init__(self,a,a2,canvas):
        self.stage_selected = False
        self.tcpPump = None
        self.manifold_started = False
        self.pump_started = False
        self.p_pump_out = 0
        self.q_pump_out = 0
        self.p_out = 0
        self.q_out = 0
        self.p_AnOut = 0
        self.q_AnOut = 0
        self.cicli_min = 0
        self.q_m_ch = 0
        self.pumpStarted = False
        self.modbus_context_list = {}
        self.modbus_identity_list = {}
        self.modbus_address_list = {}
        self.loop = None
        self.ret_m1 = False
        self.afigure = a
        self.afigure2 = a2
        self.canvas = canvas
        self._bufsize = x_size
        self.databuffer_p1 = deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_q1 = deque([0.0]*self._bufsize, self._bufsize)
        self.x = range(x_size)
        self.line_p1, = self.afigure.plot(self.x, self.databuffer_p1,"b-", label='P')
        self.line_q1, = self.afigure2.plot(self.x, self.databuffer_q1,"r-",  label='Q')

        h1, l1 = a.get_legend_handles_labels()
        h2, l2 = a2.get_legend_handles_labels()
        self.afigure.legend(h1+h2, l1+l2, loc=2, ncol=2, fontsize=10)
        self.pmax = 0
        self.qmax = 0
        self.qVmax = 0
        self.pR = 0
        self.blogFile = False
        self.oneLogged = False
        self.pipeLength = 0.0
        self.pipeDiam  = 0.0
        self.pipeType  = "ND"
        self.mixType  = "ND"
        self.mixDensity  = 0.0
        self.staticHead = 0.0
        self.p_count = 0
       

        self.adjustPMax = builder.get_object("adjustment1")
        self.adjustQMax = builder.get_object("adjustment2")
        self.time = datetime.datetime.utcnow()
        self.lastPg = deque(maxlen=designRTW*60)
        self.lastQ = deque(maxlen=designRTW*60)
        self.lblOK = builder.get_object("lblOK")
        self.lblPumpStatus = builder.get_object("lblPumpStatus")
        self.hdlf_q2 = 0
        self.hdlf_q1 = 0
        self.hdlf_k = 0
        
        self.designQmin = 0.
        self.liststore1 = builder.get_object("liststore1")
        self.liststore1.clear()

        self.mongo_CLI = MongoClient(mongo_host, int(mongo_port))
        self.mongodb = self.mongo_CLI[mongo_db]        
        stages = list(self.mongodb.stages.find({"_id":{"$in":mongo_stages}}))
        self.timeseries =  []
        for stId , st in enumerate( stages ):
            borehole = self.mongodb.boreholes.find_one({"_id":st["borehole"]})  
            for spId, s in enumerate(st["steps"]):
                self.liststore1.append([str(st["_id"]),"{0} {2}-{3} Step {1}-{5}".format(borehole["boreholeId"], spId,st["bottomLength"],st["topLength"],st["ID"],s["mixTypeType"]),str(s["_id"])])
        


    def logging_data(self, a):
        t1=datetime.datetime.utcnow()
        dt_seconds = (t1-self.time).seconds
        builder.get_object("levelbar1").set_value(len(listP1)%60+1)
        p_mA1 = self.p_AnOut
        if self.stage_selected and len(self.timeseries) > 0:
            times_item = self.timeseries.popleft()
            self.p_out = times_item["pressureGaugeManifold"]
            self.q_out = times_item["flowRateGaugeManifold"]
            builder.get_object("spButMQ").set_value(self.q_out)
            builder.get_object("spButMP").set_value(self.p_out)
        p_Eng1 = self.p_out            
        q_mA1 = self.q_AnOut
        q_Eng1 = self.q_out  
        if p_mA1 <= 4000:
            p_mA1 = 0
            p_Eng1 = 0
            
        self.lastQ.append(q_Eng1)
        self.lastPg.append(p_Eng1)            
        
        self.databuffer_p1.append( p_Eng1 )
        self.line_p1.set_ydata(self.databuffer_p1)

        self.databuffer_q1.append( q_Eng1 )
        self.line_q1.set_ydata(self.databuffer_q1)

        self.afigure.relim()
        self.afigure.autoscale_view(False, False, True)
        self.afigure2.relim()
        self.afigure2.autoscale_view(False, False, True)
        self.canvas.draw()

        listP1.append(p_Eng1)
      
        builder.get_object("txtQmax").set_text("{0} s/min {1:.2f} lit/min".format(self.qmax, self.qmax*liters_cycle))
        builder.get_object("txtPmax").set_text("{0} bar".format(self.pmax))
        if self.blogFile:
            self.oneLogged = True
            builder.get_object("btnLog").set_label("{0}".format(datetime.timedelta(seconds =dt_seconds)))
            log.info("%d;%d;%d;%d;%d;%d" % (p_mA1, p_Eng1, q_mA1, q_Eng1,self.pmax,self.qmax))
       


    def onDeleteWindow(self, *args):
        self.stoploop()
        Gtk.main_quit(*args)

    def testConnection1(self, button):
        # self.modbus_context_list
        lblTest1 = builder.get_object("lblTest1")
        manifold_host_1 = builder.get_object("txtIP1").get_text()
        manifold_port_1 = int(builder.get_object("txtPort1").get_text())
        
        if not smtConfig.has_section('Manifold_1'):
            smtConfig.add_section('Manifold_1')
        

        smtConfig.set('Manifold_1', 'host', manifold_host_1)
        smtConfig.set('Manifold_1', 'port', manifold_port_1)
        with open(sCFGName, 'wb') as configfile:
            smtConfig.write(configfile)

        self.modbus_address_list["M"] = [(manifold_host_1, manifold_port_1)]
        
        context = context_man_factory()
        self.modbus_context_list["M"] = [context]
        self.modbus_identity_list["M"] = [identity_factory("M")]
        time = 1 # 1 seconds delay
        loop = LoopingCall(f=updating_man_writer, a=(context,1,self))
        loop.start(time, now=False) # initially delay by time
        
        StartMultipleTcpServers(self.modbus_context_list["M"], self.modbus_identity_list["M"], self.modbus_address_list["M"])
        lblTest1.set_text("started")
        self.manifold_started = True
        if self.pump_started:
            self.activateRealtime()

    def on_btnConnectPump_clicked(self, button):
        lblTestPump = builder.get_object("lblTestPump")
        pump_host = builder.get_object("txtIPPump").get_text()
        pump_port = int(builder.get_object("txtPortPump").get_text())
        
        if not smtConfig.has_section('Pump'):
            smtConfig.add_section('Pump')

        smtConfig.set('Pump', 'host', pump_host)
        smtConfig.set('Pump', 'port', pump_port)
        with open(sCFGName, 'wb') as configfile:
            smtConfig.write(configfile)

        self.modbus_address_list["P"] = [(pump_host, pump_port)]
        
        context = context_pump_factory(self)
        self.modbus_context_list["P"] = [context]
        self.modbus_identity_list["P"] = [identity_factory("P")]
        time = 1 # 1 seconds delay
        loop = LoopingCall(f=updating_pump_writer, a=(context,1,self))
        loop.start(time, now=False) # initially delay by time
        
        #StartMultipleTcpServers(self.modbus_context_list["P"], self.modbus_identity_list["P"], self.modbus_address_list["P"])


        framer  = ModbusSocketFramer
        factory = ModbusServerFactory(context, framer, identity_factory("P"))
        if self.tcpPump == None:
            logInfo.info("Starting Modbus TCP Server on %s:%s" % (pump_host, pump_port))
            self.tcpPump = reactor.listenTCP(pump_port, factory, interface=pump_host)
            print "on_btnConnectPump_clicked self.tcpPump = {0}".format(self.tcpPump)
            lblTestPump.set_text("started")
            self.pump_started = True
        else:
            reactor.stop()
            print "on_btnConnectPump_clicked stop listening on self.tcpPump"
            self.tcpPump = None
            lblTestPump.set_text("stopped")
            self.pump_started = False

        if self.manifold_started:
            self.activateRealtime()

    def stoploop(self):
        if self.loop:
            if self.loop.running:
                print("loop running")
                self.loop.stop()
            else:
                print("loop not running")
        else:
            print("loop None")

    def on_btnOff_clicked(self,button):
        print("Closing application")
        self.stoploop()
        Gtk.main_quit()

    def on_btnLog_toggled(self,button):
        if not self.blogFile:
            self.time = datetime.datetime.utcnow()
                
            self.blogFile = True
        else:
            self.blogFile = False
            builder.get_object("btnLog").set_label("Log Data")

 
    def on_cmbStages_changed(self,cmb):    
        tree_iter = cmb.get_active_iter()
        if tree_iter != None:
            model = cmb.get_model()
            self.stageId = model[tree_iter][0]
            stageName = model[tree_iter][1]
            self.stepId = model[tree_iter][2]
            self.timeseries = deque()
            tmss = self.mongodb.timeseries.find({ 'stage': ObjectId(self.stageId), 'step': ObjectId(self.stepId) }).sort('timestampMinute', pymongo.ASCENDING)
            if tmss.count():
                for tv in list(tmss):
                    tv_values = [tval for tval in tv["values"].items() if tval[0] not in ('_id','v')  ]
                    tvo = collections.OrderedDict(sorted(tv_values, key=lambda t: int(t[0])))
                    for vk in tvo: 
                        self.timeseries.append({"flowRateGaugeManifold":tvo[vk]["flowRateGaugeManifold"],"pressureGaugeManifold":tvo[vk]["pressureGaugeManifold"]})
            logInfo.debug("on_cmbStages_changed selected {2} {0}-{1}".format(self.stageId,self.stepId,stageName))
            


    def on_spButMP_value_changed(self,btn):
        self.p_out = int(btn.get_value())
        logInfo.debug("on_spButMP_value_changed to {0}".format(self.p_out))
    
    def on_spButMP_change_value(self,btn):
        pass
        
           
    def on_spButMQ_value_changed(self,btn):
        self.q_out = int( btn.get_value())
        logInfo.debug("on_spButMQ_value_changed to {0}".format(self.q_out))

    def on_spButMQ_change_value(self,btn):
        pass
   
    def on_chkUseStages_toggled(self,btn):
        if btn.get_active():
            self.stage_selected = True
        else:
            self.stage_selected = False
        
    def activateRealtime(self):            
        print "activateRealtime loop"
        time_delay = 1 # 1 seconds delay
        self.loop = LoopingCall(f=self.logging_data, a=(None, builder.get_object("txtAIN1"),builder.get_object("txtAIN2"),builder.get_object("txtAIN1ENG"),builder.get_object("txtAIN2ENG"),builder.get_object("txtAIN12"),builder.get_object("txtAIN22"),builder.get_object("txtAIN1ENG2"),None,builder.get_object("txtPout"),builder.get_object("txtQout")))
        self.loop.start(time_delay, now=False) # initially delay by time
            
    
            



builder.connect_signals(Handler(a,a2,canvas))
window = builder.get_object("windowMain")
window.show_all()
reactor.run()
# Gtk.main()
