#!/usr/bin/env python
'''
Pymodbus Synchronous Client Examples

python synchronous-client.py -m localhost:5020:40001 -p localhost:502:40001 -n 10 -t 1
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
import os
import sys
import getopt
import pandas as pandas
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
    
def logPump():
    rr = pump_client_01.read_holding_registers(520,6)
    decoder = BinaryPayloadDecoder.fromRegisters(rr.registers,endian=Endian.Little)
    f_520 = decoder.decode_32bit_float()
    f_522 = decoder.decode_32bit_float()
    f_524 = decoder.decode_32bit_float()
    #log.debug("read values: " + str(rr.registers))
    log.debug("\n#### Readings ####\n##f_520=%f;f_522=%f;f_524=%f\n####" %(f_520, f_522, f_524 ))

def logCavalletto():
    rr = cavalletto_client_01.read_holding_registers(40001,8)
    log.debug("\n#### Readings ####\n##Pressure \tP(mA)=%d \tP(bar)=%d \n##Flow-rate \tQ(mA)=%d \tQ(lit/min)=%d \n####" %(rr.registers[4], rr.registers[5], rr.registers[6],rr.registers[7] ))    

def peff(p_gauge, q):
    p_hdlf = hdlf[0]*q**2+hdlf[1]*q+hdlf[0]
    p_hdlf = p_hdlf*pipe_length
    log.debug("P_hdlf %f bar" % p_hdlf)
    return p_gauge + static_head - p_hdlf
    
def check_values(p_client,p_first_register, m_client, m_first_register):
    exp_item = OrderedDict()
    log.debug("check_values %s %s" % (p_client,m_client))
    m_start_address = m_first_register-1  # inizia a leggere da m_first_register-1 e prendi gli N successivi,escluso m_start_address
    m_rr = m_client.read_holding_registers(m_start_address,8)
    # pressione in mA
    p_mA = m_rr.registers[4-1]
    p_bar = scale(p_p1,p_p2,p_mA)
    # portata in mA
    q_mA = m_rr.registers[6-1]
    q_bar = scale(q_p1,q_p2,q_mA)   
    p_eff = peff(p_bar, q_bar)
    log.debug("\n#### Readings ####\n##Pressure \tP(mA)=%d \tP(bar)=%d \n##Flow-rate \tQ(mA)=%d \tQ(lit/min)=%d Peff = %f\n####" %(m_rr.registers[4-1], p_bar, m_rr.registers[6-1],q_bar, p_eff )) 
    exp_item["p_gauge"] = p_bar
    exp_item["p_eff"] = p_eff
    exp_item["R"] = R
    exp_item["q_bar"] = q_bar
    p_start_address = p_first_register-1 # inizia a leggere da m_first_register-1 e prendi gli N successivi,escluso m_start_address
    p_rr = p_client.read_holding_registers(p_start_address+500,100)
    p_out = p_rr.registers[16-1]
    p_max = p_rr.registers[60-1]
    mw_520 = p_rr.registers[20-1]
    np_max = R + p_out - p_eff
    decoder = BinaryPayloadDecoder.fromRegisters(p_rr.registers[22-1:26-1],endian=Endian.Little)
    f_522 = decoder.decode_32bit_float()
    f_524 = decoder.decode_32bit_float()
    log.debug("\n#### Readings ####\n##c_out=%f;q_out=%f;p_out=%d;p_max=%d;np_max=%d\n####" %(mw_520, f_522, p_out,p_max,np_max ))
    exp_item["p_out"] = p_out
    exp_item["p_max"] = p_max
    exp_item["p_max_new"] = R + p_out - p_eff
    return exp_item
    

def main(argv):
    syntax = os.path.basename(__file__) + " -m <manifold host:port:first register> -p <pump host:port:first register> -n <number of loops> -t <sleep_time>"
    manifold_hostport = "localhos:502"
    pump_hostport = "localhos:5020"   
    export_xls = "export.xls"
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
    for i in range(loops):
        exp_item = check_values(p_client,p_first_register, m_client, m_first_register)
        exp_items.append(exp_item)
        time.sleep(sleep_time)
        log.debug("########################### Iteration %02d terminated" % i)
    p_client.close()
    log.debug("%s disconnected" % pump_hostport)
    m_client.close()
    log.debug("%s disconnected" % manifold_hostport)
    bh_df = pandas.DataFrame(exp_items)
    export_xls_path = os.path.join(sCurrentWorkingdir,export_xls)
    bh_df.to_excel(export_xls_path,sheet_name="data",columns =exp_item.keys(), index=False)

    
if __name__ == "__main__":
    main(sys.argv[1:])