# -*- coding: utf-8 -*-
#!/usr/bin/env python
'''
Pymodbus Synchronous Client Examples

python synchronous-client.py -m localhost:5020:40001 -p localhost:502:40001 -n 10 -t 1
'''
#---------------------------------------------------------------------------# 
# import the various server implementations
#---------------------------------------------------------------------------# 
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
from pymodbus.constants import Endian
#from pymodbus.client.sync import ModbusUdpClient as ModbusClient
#from pymodbus.client.sync import ModbusSerialClient as ModbusClient
from twisted.internet.task import LoopingCall
#---------------------------------------------------------------------------# 
# configure the client logging
#---------------------------------------------------------------------------# 
import logging, time
import os
import sys
import getopt
import datetime
import pandas as pandas
from openpyxl import load_workbook
from collections import OrderedDict


logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)
low, high = 4, 20 # mA
low_p, high_p = 0, 100 # pressure (P in bar)
low_q, high_q = 5, 50 # flow-rate (Q in lit/min)
p_p1 = (low,low_p)
p_p2 = (high,high_p)
q_p1 = (low,low_q)
q_p2 = (high,high_q)

hdlf = (0.0000745,0.000128,0.0)
boreholecollar_elevation = 20.
pipe_length = 90.
water_elevation = -40.
stage_elevation = -60.
gauge_h = 0.7
grout_spec_density = 1.8
R=50

DEFAULT_BAR = 40
DEFAULT_CICLI = 20

STAGE_LENGTH = 5.0

CUMULATIVE_VOLUME = 298.0*STAGE_LENGTH

MIX_TYPE = 1
BUPSTAGE = False
P_PREVIOUS = 30

h_grout = boreholecollar_elevation - stage_elevation
h_water = boreholecollar_elevation - water_elevation
grout_head = 0.0980*grout_spec_density*(h_grout + gauge_h)
water_head = 0.0980*(h_grout - h_water )
static_head = grout_head - water_head
log.debug("h_grout %f" % h_grout)
log.debug("h_water %f" % h_water)
log.debug("water head %f bar" % water_head)
log.debug("grout head %f bar" % grout_head)
log.debug("static head %f bar" % static_head)

sCurrentWorkingdir = os.getcwd()

def scale(p1,p2,x):
    x1, y1 = p1
    x2, y2 = p2
    y = (x-x1)*(y2-y1)/(x2-x1)+y1
    return y

def modbus_client(manifold_hostport):
    first_register = 40001
    splitted = manifold_hostport.split(":")
    host = splitted[0]
    port = int(splitted[1])
    if len(splitted) == 3:
        first_register = int(splitted[2])
    return ModbusClient(host, port=port), first_register
    
  

def peff(p_gauge, q):
    p_hdlf = hdlf[0]*q**2+hdlf[1]*q+hdlf[0]
    p_hdlf = p_hdlf*pipe_length
    log.debug("P_hdlf %f bar" % p_hdlf)
    return p_gauge + static_head - p_hdlf, static_head, p_hdlf

BAR_INPUT = 0.0
    
def loop():
    log.debug("loop started %f " % BAR_INPUT )
    
    log.debug("loop terminated")


def check_mix_A(V,Peff,Pr):
    V1 = 0.1*1000.0
    V2 = 0.3*1000.0
    V3 = 0.5*1000.0
    V4 = 0.8*1000.0
    P1 = 0.1
    P2 = 0.5
    P3 = 0.8
    p_bandwith = 0.01 # define outside
    deltaP = Pr-Peff
    if deltaP <= p_bandwith:
        return True, True, "mix_A", False # Residual achieved, stop injection, current Mix Type
    else:
        if V >= V3:
            if Peff < P3*Pr:
                return False, True, "mix_B", False # Residual not achieved, stop injection, next Mix Type
            else:
                return False, False, "mix_A", False # Residual not achieved,don't stop injection, current Mix Type
        elif V >= V2:
            if Peff < P2*Pr:
                return False, True, "mix_B", False # Residual not achieved, stop injection, next Mix Type
            else:
                return False, False, "mix_A", False # Residual not achieved,don't  stop injection, current Mix Type
        elif V >= V1:
            if Peff < P1*Pr:
                return False, True, "mix_B", False # Residual not achieved, stop injection, next Mix Type
            else:
                return False, False, "mix_A", False # Residual not achieved, don't stop injection, current Mix Type
        else:
            return False, False, "mix_A", False # Residual not achieved, don't stop injection, current Mix Type
           

           
def check_upstage(MixType,Peff,Pa):
    if Peff > Pa:
        return True, True, MixType, False # Residual achieved from previous stage, stop injection, current Mix Type
    else:
        return False, False, MixType, True # Residual not achieved, stop injection, current Mix Type, intermittent Grouting 

def check_pressure(Peff, Ptest , Pr, MixType):
    if Peff < Ptest*Pr:
        return False, True, MixType+1, False # Residual not achieved, stop injection, next Mix Type, No intermittent Grouting 
    else:
        return False, False, MixType, False # Residual not achieved,don't stop injection, keep current Mix Type, No intermittent Grouting 

def check_pressure_intermittent(Peff, Ptest , Pr, MixType):
    if Peff < Ptest*Pr:
        return False, False, MixType, True # Residual not achieved, stop injection, next Mix Type, No intermittent Grouting 
    else:
        return False, False, MixType, False # Residual not achieved,don't stop injection, keep current Mix Type, No intermittent Grouting 


def check_mix(V,MixType,Peff,Pr,bUpstage, Pa):
    # TODO start define outside    
    V1 = 0.1*1000.0
    V2 = 0.3*1000.0
    V3 = 0.5*1000.0
    V4 = 0.8*1000.0
    V5 = 2.0*1000.0
    P1 = 0.1
    P2 = 0.5
    P3 = 0.8
    p_bandwith = 0.01 
    # end define outside
    # init to: Residual achieved, stop injection, current Mix Type
    retTuple = (True, True, MixType, False)
    deltaP = Pr-Peff
    if deltaP <= p_bandwith:
        retTuple = (True, True, MixType, False) # Residual achieved, stop injection, current Mix Type
    else:
        if V >= V5:
            if bUpstage:
                retTuple = check_upstage(MixType,Peff,Pa)
            else:
                retTuple = check_pressure_intermittent(Peff, P3 , Pr, MixType) 
        elif V >= V4:
            if bUpstage:
                retTuple = check_upstage(MixType,Peff,Pa)
            else:
                if Peff < P2*Pr:
                    retTuple =( False, True, MixType+1, False )# Residual not achieved, stop injection, next Mix Type
                else:
                    retTuple = check_pressure_intermittent(Peff, P3 , Pr, MixType)
        elif V >= V3:
            retTuple = check_pressure(Peff, P3 , Pr, MixType)
        elif V >= V2:
            retTuple = check_pressure(Peff, P2 , Pr, MixType)
        elif V >= V1:
            retTuple = check_pressure(Peff, P1 , Pr, MixType)            
        else:
            retTuple = ( False, False, MixType, False )# Residual not achieved, don't stop injection, continue with current Mix Type
    return retTuple
           




            
def check_values(p_client,p_first_register, m_client, m_first_register,sleep_time):
    global BAR_INPUT, CUMULATIVE_VOLUME
    exp_item = OrderedDict()
    log.debug("check_values %s %s" % (p_client,m_client))
    # m_start_address = m_first_register-1  # if zero_mode=False => inizia a leggere da Manifold a partire da m_first_register-1 per gli N successivi,escluso m_start_address
    #################################### CAVALLETTO
    m_start_address = m_first_register
    m_rr = m_client.read_holding_registers(m_start_address,35)
    # Machine ID
    m_ID = m_rr.registers[1-1]
    # IP ADDR. da 32,33,34 e 35
    sIPAddr = "%d.%d.%d.%d" %  tuple(m_rr.registers[32-1:36-1])
    # pressione in mA in posizione 4
    p_mA = m_rr.registers[4-1]
    p_bar = scale(p_p1,p_p2,p_mA)
    # portata in mA in posizione 6
    q_mA = m_rr.registers[6-1]
    q_bar = scale(q_p1,q_p2,q_mA)   
    CUMULATIVE_VOLUME += q_bar*(sleep_time/60.)
    p_eff, static_head, p_hdlf = peff(p_bar, q_bar)
    log.debug("\n#### Readings from %s (%s)####\n##Pressure \tP(mA)=%d \tP(bar)=%d \n##Flow-rate \tQ(mA)=%d \tQ(lit/min)=%d Peff = %f\n####" %(m_ID, sIPAddr,m_rr.registers[4-1], p_bar, m_rr.registers[6-1],q_bar, p_eff )) 
    exp_item["TIME"] = datetime.datetime.utcnow().strftime("%Y%m%d %H:%M:%S.%f")
    exp_item["m_ID"] = m_ID
    exp_item["m_IP"] = sIPAddr
    exp_item["STAGE_LENGTH"] = STAGE_LENGTH
    exp_item["p_gauge"] = p_bar
    exp_item["static_head"] = static_head
    exp_item["p_hdlf"] = p_hdlf
    exp_item["p_eff"] = p_eff
    exp_item["R"] = R
    exp_item["q_bar"] = q_bar
    exp_item["q_cum"] = CUMULATIVE_VOLUME
    volume_m = CUMULATIVE_VOLUME/STAGE_LENGTH
    exp_item["volume_m"] = volume_m
    BAR_INPUT = q_bar
    #################################### INIETTORE
    #p_start_address = p_first_register-1 # if zero_mode=False => inizia a leggere da m_first_register-1 e prendi gli N successivi,escluso m_start_address
    p_start_address = p_first_register
    p_rr = p_client.read_holding_registers(p_start_address+500,100)
    p_out = p_rr.registers[16-1]
    p_max = p_rr.registers[60-1]
    mw_520 = p_rr.registers[20-1]
    np_max = R + p_out - p_eff
    dP_pump = p_max - p_out
    dP_borehole = R - p_eff
    decoder = BinaryPayloadDecoder.fromRegisters(p_rr.registers[22-1:26-1],endian=Endian.Little)
    f_522 = decoder.decode_32bit_float()
    f_524 = decoder.decode_32bit_float()
    log.debug("\n#### Readings ####\n##p_bar=%f;p_eff=%f;p_out=%d;p_max=%d;np_max=%d;q=%f;V=%f\n####" %(p_bar, p_eff, p_out,p_max,np_max,q_bar,CUMULATIVE_VOLUME))
    bR, bStop, next_mix_type, bIntermittent = check_mix(volume_m, MIX_TYPE, p_eff,R,BUPSTAGE, P_PREVIOUS ) 
    #check_mix(volume_m,p_eff,R)
    exp_item["stop"] = bStop
    exp_item["ok R"] = bR
    exp_item["next mix_type"] = next_mix_type
    exp_item["p_out"] = p_out
    exp_item["p_max"] = p_max
    exp_item["p_max_new"] = np_max
    exp_item["dP_pump"] = dP_pump
    exp_item["dP_borehole"] = dP_borehole
    return exp_item

def check_alarms(reg_504):
    b_ok = True
    allarmi = { 0:"All_Max_Pressione",
                                1:"All_Emergenza",
                                2:"All_TermicoPompa",
                                3:"All_TermicoScambiatore1",
                                4:"All_LivelloOlio",
                                5:"All_Pressostato",
                                6:"All_Configurazione PLC",
                                7:"All_Batteria",
                                8:"All_termicoScambiatore2",
                                9:"All_TermicoPompaRicircolo",
                                10:"All_TemperaturaVasca"
                                }
    for key in reg_504:
        if reg_504[key]:
            log.error("Allarme %s" % allarmi[key])
            b_ok = False        
    return b_ok
    
    
def start_iniettore(p_client):
    b_ok = False
    n_numReg = 5
    # leggo 502 a 506 per verificare bit di controllo
    p_rr = p_client.read_holding_registers(40502,n_numReg)
    decoder = BinaryPayloadDecoder.fromRegisters(p_rr.registers,endian=Endian.Little)
    reg={}
    regnum = 502
    for i in range(n_numReg):
        bits_50x = decoder.decode_bits()
        bits_50x += decoder.decode_bits()
        reg[regnum+i] = bits_50x
    if reg[502][4]:
        log.error("Pompa in allarme")
    else:
        if reg[502][6]:
            log.debug("Pompa olio on")
            if reg[502][7]:
                log.error("Ciclo Iniettore ON")
            else:
                log.debug("Ciclo Iniettore OFF")
                # %MW502:X10 Macchina pronta per comando remoto
                b_ok = reg[502][10]
                if b_ok:
                    log.debug("Macchina pronta per comando remoto")
                else:
                    log.error(u"Macchina non è pronta per comando remoto")
                b_ok &= check_alarms(reg[504])
                if b_ok:
                    log.debug("...nessun allarme rilevato")
                    p_comandi_remoto = p_client.read_holding_registers(40560,3)
                    remote_reg = [0]*3
                    remote_reg = p_comandi_remoto.registers
                    log.debug("COMANDO BAR DA REMOTO IMPOSTATO a %d" %  remote_reg[0]) # %MW560  16 bit 0-100 bar	COMANDO BAR DA REMOTO
                    log.debug("COMANDO NUMERO CICLI MINUTO DA REMOTO a %d" %  remote_reg[2]) # %MW562 16 bit < 40	COMANDO NUMERO CICLI MINUTO DA REMOTO
                    remote_reg[0] = DEFAULT_BAR
                    remote_reg[2] = DEFAULT_CICLI
                    rq = p_client.write_registers(40560, remote_reg)
                    b_ok  = rq.function_code < 0x80     # test that we are not an error
                    if b_ok:
                        bits_552 = [False]*16
                        bits_552[2] = True # %MW552:X2	START INIET. DA REMOTO
                        builder = BinaryPayloadBuilder(endian=Endian.Little)
                        builder.add_bits(bits_552)
                        reg_552 = builder.to_registers()
                        rq = p_client.write_register(40552, reg_552[0])
                        b_ok  = rq.function_code < 0x80     # test that we are not an error
                    else:
                        log.error("start_iniettore SET Comandi BAR e CICLI REMOTO fallito!")
                else:
                    log.debug("...verificare allarmi rilevati")
        else:
            log.error("Pompa olio OFF")
    return b_ok

def stop_iniettore(p_client):
    b_ok = False
    bits_552 = [False]*16
    bits_552[3] = True # %MW552:X3	STOP INIET.DA REMOTO
    builder = BinaryPayloadBuilder(endian=Endian.Little)
    builder.add_bits(bits_552)
    reg_552 = builder.to_registers()
    rq = p_client.write_register(40552, reg_552[0])
    b_ok  = rq.function_code < 0x80     # test that we are not an error
    return b_ok
    
def main(argv):
    syntax = os.path.basename(__file__) + " -m <manifold host:port:first register> -p <pump host:port:first register> -n <number of loops> -t <sleep_time>"
    manifold_hostport = "localhos:502"
    pump_hostport = "localhos:5020"   
    dt = datetime.datetime.utcnow()
    export_xls = "export_%d%02d%02d.xlsx" % (dt.year,dt.month,dt.day)
    loops = 1
    sleep_time = 1
    try:
        opts = getopt.getopt(argv, "hm:p:n:t:f:", ["manifold=", "pump=", "loops=", "time=", "file="])[0]
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
        elif opt in ("-p", "--pump"):
            pump_hostport = arg
        elif opt in ("-m", "--manifold"):
            manifold_hostport = arg
        elif opt in ("-n", "--loops"):
            loops = int(arg)
        elif opt in ("-t", "--time"):
            sleep_time = float(arg)
        elif opt in ("-f", "--file"):
            export_xls = arg
    p_client, p_first_register = modbus_client(pump_hostport)
    m_client, m_first_register = modbus_client(manifold_hostport)
    p_client.connect()
    log.debug("%s connected" % pump_hostport)
    m_client.connect()
    log.debug("%s connected" % manifold_hostport)
    log.debug("########################### Starting %02d iterations" % loops)
    exp_items = []
    b_ok = start_iniettore(p_client)
    # devo aspettare 2 secondi con il simulatore perchè si accorge dopo che il registro è cambiato
    time.sleep(2)
    for i in range(loops):
        exp_item = check_values(p_client,p_first_register, m_client, m_first_register,sleep_time)
        exp_items.append(exp_item)
        time.sleep(sleep_time)
        log.debug("########################### Iteration %02d terminated" % i)
    print stop_iniettore(p_client)
    p_client.close()
    log.debug("%s disconnected" % pump_hostport)
    m_client.close()
    log.debug("%s disconnected" % manifold_hostport)
    bh_df = pandas.DataFrame(exp_items)
    export_xls_path = os.path.join(sCurrentWorkingdir,export_xls)
    writer = pandas.ExcelWriter(export_xls_path, engine='openpyxl')
    if os.path.isfile(export_xls_path):
        book = load_workbook(export_xls_path)
        writer.book = book
        writer.sheets = dict((ws.title, ws) for ws in book.worksheets)
    bh_df.to_excel(writer,sheet_name="data",columns =exp_item.keys(), index=False)
    writer.save()

    
if __name__ == "__main__":
    main(sys.argv[1:])