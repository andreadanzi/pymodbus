# -*- coding: utf-8 -*-
#!/usr/bin/env python
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException
from pymodbus.pdu import ExceptionResponse
import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)
# test connettività
host = '127.0.0.1'
port = 5020
test_reg_no = 0 # test the expected value (Machine ID, defaukt is 0x5100)  
test_value = 0x5100 # 20736
starting_register = 40001
client = ModbusClient(host, port=port)
try:
    client.connect()
    log.info("Connessione Modbus TCP a {0}:{1} effettuata".format(host,port))
    # scegliere registro e assert da verificare
    rr = client.read_holding_registers(starting_register,10)      
    if isinstance(rr ,ExceptionResponse):
        log.error("Errore su read_holding_registers {0}: {1}".format(starting_register,rr))
    else:
        log.info("{1} Regsitri letti {0}".format(rr.registers,len(rr.registers)))
        if rr.registers[test_reg_no] == test_value:   
            log.info("OK - Su registro {0} il valore {1} == {2}".format(test_reg_no,rr.registers[test_reg_no],test_value))
        else:
            log.error("Errore su registro {0}, valore {1} != {2}".format(test_reg_no,rr.registers[test_reg_no],test_value))
    client.close()    
    log.info("Chiusa la connessione Modbus TCP a {0}:{1}".format(host,port))
except ConnectionException as cex:
    log.error("Errore connessione Modbus TCP {1}:{2}. {0}".format(cex,host,port))
exit(-99)

















# test iniettore
client = ModbusClient('localhost', port=5020)
client.connect()
# verifico i primi 2 registri di cui so qualcosa
rr = client.read_holding_registers(40001,2)
print rr.registers
assert(rr.registers[0] == 12345)   # test the expected value (pump test è 12345)
# leggo 560, COMANDO BAR DA REMOTO
rr = client.read_holding_registers(40560,1)
print rr.registers
# Incremento di 1 il registro 560, COMANDO BAR DA REMOTO
rq = client.write_register(40560, rr.registers[0]+1)
assert(rq.function_code < 0x80)     # test that we are not an error
# Leggo STATO INIETTORE CON ALLARMI
print "Leggo STATO INIETTORE CON ALLARMI"
rr = client.read_holding_registers(40502,5)
decoder = BinaryPayloadDecoder.fromRegisters(rr.registers,endian=Endian.Little)
# 502
bits_502 = decoder.decode_bits()
bits_502 += decoder.decode_bits()
# 503
bits_503 = decoder.decode_bits()
bits_503 += decoder.decode_bits()
# 504
bits_504 = decoder.decode_bits()
bits_504 += decoder.decode_bits()
# 505
bits_505 = decoder.decode_bits()
bits_505 += decoder.decode_bits()
# 506
bits_506 = decoder.decode_bits()
bits_506 += decoder.decode_bits()


if bits_502[4] == False and bits_502[10] == True:
    print "Macchina senza allarmi e pronta per comando remoto"
    # Leggo START INIETTORE DA REMOTO reg 522
    rr = client.read_holding_registers(40552,1)
    decoder = BinaryPayloadDecoder.fromRegisters(rr.registers,endian=Endian.Little)
    as_bits = decoder.decode_bits()
    as_bits += decoder.decode_bits()
    print "522 " + str(as_bits)
    if bits_506[2]:
        print u"Macchina già avviata con comando remoto"
        if as_bits[3] == False:
            print u"STOP INIETTORE DA REMOTO è abassato"
            # Accendo bit STOP INIETTORE DA REMOTO
            as_bits[3] = 1
            builder = BinaryPayloadBuilder(endian=Endian.Little)
            builder.add_bits(as_bits)
            reg=builder.to_registers()
            print reg
            rq = client.write_register(40552, reg[0])
            assert(rq.function_code < 0x80)     # test that we are not an error
        else:
            print u"STOP INIETTORE DA REMOTO è ancora alzato"  
    else:
        if as_bits[2] == False:
            print u"START INIETTORE DA REMOTO è abassato"
            # Accendo bit START INIETTORE DA REMOTO
            as_bits[2] = 1
            builder = BinaryPayloadBuilder(endian=Endian.Little)
            builder.add_bits(as_bits)
            reg=builder.to_registers()
            print reg
            rq = client.write_register(40552, reg[0])
            assert(rq.function_code < 0x80)     # test that we are not an error
        else:
            print u"START INIETTORE DA REMOTO è ancora alzato"        
rr = client.read_holding_registers(40552,1)
decoder = BinaryPayloadDecoder.fromRegisters(rr.registers,endian=Endian.Little)
# print unpack_bitstring(decoder._payload)
as_bits = decoder.decode_bits()
as_bits += decoder.decode_bits()
print as_bits
client.close()