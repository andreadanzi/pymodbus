# -*- coding: utf-8 -*-
#!/usr/bin/env python
import os, sys, getopt, time, csv, datetime
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
import numpy as np
import logging
import logging.handlers


logInfo = logging.getLogger("info")
logInfo.setLevel(logging.DEBUG)

fileInfo_handler = logging.handlers.RotatingFileHandler("{0}.log".format(os.path.basename(__file__).split(".")[0]), maxBytes=5000000,backupCount=5)
fileInfo_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
fileInfo_handler.setFormatter(formatter)
logInfo.addHandler(fileInfo_handler)




"""

Iniettore Lorenzetto - IP 10.243.37.113;
Iniettore Lorenzetto - IP 10.243.37.114;
Iniettore Lorenzetto - IP 10.243.37.115;
Iniettore Lorenzetto - IP 10.243.37.116;

Cavalletto Geomisure - IP 10.243.37.7;
Cavalletto Geomisure - IP 10.243.37.8;

"""


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
             "%MW502:X14":"ND",
             "%MW502:X15":"ND",
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
             "%MW504:X13":"ND",
             "%MW504:X14":"ND",
             "%MW504:X15":"ND",
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
             "%MW506:X10":"ND",
             "%MW506:X11":"ND",
             "%MW506:X12":"ND",
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
             "%MW552:X10":"ND",
             "%MW552:X11":"ND",
             "%MW552:X12":"ND",
             "%MW552:X13":"ND",
             "%MW552:X14":"RESET TOTALIZ. GIORNALIERI REMOTO",
             "%MW552:X15":"RESET TOTALIZ. PERPETUI REMOTO"}

def main(argv):
    
    syntax = "python " + os.path.basename(__file__) + " -p <port> -i <ip address> -t <type of equipment>\n\nOptions\n\t-a if IP are listed on a ip.txt file, example: \nP,10.243.37.113,5021\nP,10.243.37.114,502\nP,10.243.37.115,502\nP,10.243.37.116,502\nM,10.243.37.7,502\nM,10.243.37.8,502"
    eqtype=""
    eqport=-99
    eqip=""
    allIp = False
    logData = False
    try:
        opts = getopt.getopt(argv, "hp:i:t:al", ["port=", "ipaddress=","type=","all","log"])[0]
    except getopt.GetoptError:
        print syntax
        sys.exit(1)
    for opt, arg in opts:
        if opt == '-h':
            print syntax
            sys.exit()
        elif opt in ("-i", "--ipaddress"):
            eqip = arg
        elif opt in ("-a", "--all"):
            allIp = True
        elif opt in ("-l", "--log"):
            logData = True
        elif opt in ("-p", "--port"):
            eqport = int(arg)
        elif opt in ("-t", "--type"):
            eqtype = arg
    
    iptest_list = []

    if not allIp:
        while eqtype == "":
            eqtype = raw_input("Please enter P for Pump and M for Manifold: ")
    
        while eqip == "":
            eqip = raw_input("Please enter the ip adrress: ")
        
        while eqport < 0:
            eqport = int(raw_input("Please enter the TCP port (enter 502 for default): "))
        
        if eqtype !="" and eqip !="" and eqport > 0:
            iptest_list.append((eqtype,eqip,eqport))
        else:
            print syntax
            sys.exit(1)
    else:
        with open('ip.txt', 'rb') as csvfile:
            spamreader = csv.reader(csvfile, delimiter=',')
            for row in spamreader:
                iptest_list.append(tuple(row))
    with open('ctest_data_logged.csv', 'wb') as csvfile:
        spamwriter = csv.writer(csvfile, delimiter=';')
        while True:
            print "press ^C to stop the test"
            for item_ip in iptest_list:
                eqtype = item_ip[0]
                eqip = item_ip[1]
                eqport = int(item_ip[2])
                logInfo.info("Test {0} on {1}:{2} #################".format(eqtype,eqip,eqport))
                print "Test {0} on {1}:{2} #################".format(eqtype,eqip,eqport)
                client = ModbusClient(eqip, port=eqport)
                ret_p=client.connect()
                if ret_p==True:
                    print "Equipment type {0} connected on {1}:{2}. Connection test passed!".format(eqtype,eqip, eqport)
                    if eqtype=='M':
                        rr_m = client.read_holding_registers(0,48)
                        assert(len(rr_m.registers)==48)
                        assert(rr_m.registers[0]==0x5200)
                        print "Manifold first register value = {0}, OK!".format(rr_m.registers[0])
                        logInfo.info("\tManifold first register value = {0}, OK!".format(rr_m.registers[0]))
                        sIPAddr = "%d.%d.%d.%d" %  tuple(rr_m.registers[32-1:36-1])
                        print "Manifold IP address {0}".format(sIPAddr)
                        logInfo.info("\tManifold IP address {0}".format(sIPAddr))
                        rr1 = client.read_holding_registers(103,10)
                        reg104_1 = tuple(rr1.registers )
                        print "\tANA to ENG Pressure parameters: from {0}-{1} to {2}-{3}".format(reg104_1[0],reg104_1[1],reg104_1[2],reg104_1[3])
                        logInfo.info("\t\tANA to ENG Pressure parameters: from {0}-{1} to {2}-{3}".format(reg104_1[0],reg104_1[1],reg104_1[2],reg104_1[3]))
                        p_fit = np.polyfit([reg104_1[0],reg104_1[1]],[reg104_1[2],reg104_1[3]],1)
                        print "\t\tPressure: slope={0}, intercept={1}".format(p_fit[0]/10.,p_fit[1]/10.)
                        logInfo.info("\t\t\tPressure: slope={0}, intercept={1}".format(p_fit[0]/10.,p_fit[1]/10.))
                        print "\tANA to ENG Flowrate parameters: from {0}-{1} to {2}-{3}".format(reg104_1[6],reg104_1[7],reg104_1[8],reg104_1[9])
                        logInfo.info("\t\tANA to ENG Flowrate parameters: from {0}-{1} to {2}-{3}".format(reg104_1[6],reg104_1[7],reg104_1[8],reg104_1[9]))
                        q_fit = np.polyfit([reg104_1[6],reg104_1[7]],[reg104_1[8],reg104_1[9]],1)
                        print "\t\tFlowrate: slope={0}, intercept={1}".format(q_fit[0]/10.,q_fit[1]/10.)
                        logInfo.info("\t\t\tFlowrate: slope={0}, intercept={1}".format(q_fit[0]/10.,q_fit[1]/10.))
                        logInfo.info("Test on Manifold terminated!")
                        datarow = (datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],rr_m.registers[3],rr_m.registers[4] ,rr_m.registers[5] ,rr_m.registers[6]  )
                        if logData:
                            spamwriter.writerow(datarow)
                        print "Test on Manifold terminated!"
                    elif eqtype == 'P':
                        default_550 = 2
                        rq = client.write_register(550,default_550,unit=1)
                        assert(rq.function_code < 0x80)
                        rr_p = client.read_holding_registers(500,100,unit=1)
                        assert(len(rr_p.registers)==100)
                        liststore = []
                        for idx in [0,2,4,6,12,13,14,15,16,20,50,52,60,62]:
                            if idx in (2,4,6,52):
                                decoder = BinaryPayloadDecoder.fromRegisters(rr_p.registers[idx:idx+1],endian=Endian.Little)
                                bits = decoder.decode_bits()
                                bits += decoder.decode_bits()
                                for ib, b in enumerate(bits):
                                    if b:
                                        sCode = "%MW5{0:02d}:X{1}".format(idx,ib)
                                        liststore.append([sCode,reg_descr[sCode], str( b ) ])
                            else:
                                sCode = "%MW5{0:02d}".format(idx)
                                liststore.append([sCode, reg_descr[sCode], str( rr_p.registers[idx]) ])            
                        
                        for item in liststore:
                            print "{0} = \t{2}\t\t{1}".format(item[0],item[1],item[2])
                            logInfo.info("\t{0} = \t{2}\t\t{1}".format(item[0],item[1],item[2]))
                        print rr_p.registers[0]
                        assert(rr_p.registers[0]==default_550) # registro 500 contiene quanto settato in 550
                        print "Pump register 500 = {0}, ok!".format(rr_p.registers[0])
                        logInfo.info("Test on Pump terminated!")
                        print "Test on Pump terminated!"
                
                    client.close()
                    time.sleep(0.1)
                else:
                    print "ERROR: Unable to connect to equipment type {0} on {1}:{2}. Connection test failed!".format(eqtype,eqip, eqport)
                    logInfo.error("Unable to connect to equipment type {0} on {1}:{2}. Connection test failed!".format(eqtype,eqip, eqport))
                    time.sleep(0.1)
        

if __name__ == "__main__":
    main(sys.argv[1:])