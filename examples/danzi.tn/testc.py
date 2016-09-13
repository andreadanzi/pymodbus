# -*- coding: utf-8 -*-
#!/usr/bin/env python
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.exceptions import ConnectionException
from pymodbus.pdu import ExceptionResponse
import logging, time
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)
# test connettività
host = '10.243.37.8'
port = 502
test_reg_no = 0 # test the expected value (Machine ID, defaukt is 0x5100)
test_value = 20992 # 0x5200 => 20992
starting_register = 0 #cambiato da 40001 -1
client = ModbusClient(host, port=port)
try:
    client.connect()
    log.info("Connessione Modbus TCP a {0}:{1} effettuata".format(host,port))
    for ti in range(10):
        # scegliere registro e assert da verificare
        rr = client.read_holding_registers(0,36)
        if isinstance(rr ,ExceptionResponse):
            log.error("Errore su read_holding_registers {0}: {1}".format(starting_register,rr))
        else:
            log.info("{1} Regsitri letti {0}".format(rr.registers,len(rr.registers)))
            if rr.registers[test_reg_no] == test_value:
                log.info("OK - Su registro {0} il valore {1} == {2}".format(test_reg_no,rr.registers[test_reg_no],test_value))
                sIPAddr = "%d.%d.%d.%d" %  tuple(rr.registers[32-1:36-1])
                log.info("indirizzo IP presente nei registri {0}".format(sIPAddr))
                # AIN1 pressione in mA in posizione 4
                p_mA = rr.registers[4-1]# AIN1 pressione in mA in posizione 4
                #TODO AIN1 ENG pressione in ??? in posizione 5; sicuri che è un UINT16
                p_Eng = rr.registers[5-1]
                # AIN2 portata in mA in posizione 6
                q_mA = rr.registers[6-1]
                #TODO AIN2 ENG portata in ??? in posizione 7; sicuri che è un UINT16
                q_Eng = rr.registers[7-1]
                log.info("lettura AIN1 P(mA/bar) = {0}/{2}, AIN2 Q(mA/lit/min) = {1}/{3}".format(p_mA,q_mA,p_Eng,q_Eng))
                #lettura START SCALE e STOP SCALE
                rr = client.read_holding_registers(104-1,10)   #cambiato da 40104
                if isinstance(rr ,ExceptionResponse):
                    log.error("Errore su read_holding_registers {0}: {1}".format(104,rr)) #cambiato da 40104
                else:
                    log.info("{1} Regsitri letti {0}".format(rr.registers,len(rr.registers)))
                    log.info("AIN1 {0}-{1}=>{2}-{3} AIN2 {4}-{5}=>{6}-{7}".format(rr.registers[0],rr.registers[1],rr.registers[2],rr.registers[3],rr.registers[6],rr.registers[7],rr.registers[8],rr.registers[9]))
                    # AIN1 4000-20000=>0-1000 AIN2 4000-20000=>0-2000
            else:
                log.error("Errore su registro {0}, valore {1} != {2}".format(test_reg_no,rr.registers[test_reg_no],test_value))
        log.info("################ iterazione {0} conclusa".format(ti))
        time.sleep(1.)
    client.close()
    log.info("Chiusa la connessione Modbus TCP a {0}:{1}".format(host,port))
except ConnectionException as cex:
    log.error("Errore connessione Modbus TCP {1}:{2}. {0}".format(cex,host,port))

# compare spesso errore di connessione
# ERROR:pymodbus.client.sync:Connection to (192.168.0.36, 502) failed: [Errno 111] Connection refused
