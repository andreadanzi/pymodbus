# -*- coding: utf-8 -*-
#!/usr/bin/env python
from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
from pymodbus.constants import Endian
from pymodbus.exceptions import ConnectionException
from pymodbus.pdu import ExceptionResponse
import logging, time
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)
# test connettività
liters_cycle = 2.8299 # 230(103-50.2) - 230 corsa, 103 diam. esterno, 50.2 diam interno
host = 'localhost'
port = 5320
test_reg_no = 0 # test su MW500
test_value = 1 #
default_bar = 10
default_cicli = 40
starting_register = 500 # 40500
client = ModbusClient(host, port=port)
try:
    client.connect()
    log.info("Connessione Modbus TCP a {0}:{1} effettuata".format(host,port))
    # scegliere registro e assert da verificare
    rr = client.read_holding_registers(starting_register,100,unit=1)
    if isinstance(rr ,ExceptionResponse):
        log.error("Errore su read_holding_registers {0}: {1}".format(starting_register,rr))
    else:
        log.info("{1} Regsitri letti {0}".format(rr.registers,len(rr.registers)))
        if rr.registers[test_reg_no] == test_value:
            log.info("OK - Su registro {0} il valore {1} == {2}".format(test_reg_no,rr.registers[test_reg_no],test_value))
            log.info("MW500 {0} (UNIT16)".format(rr.registers[0]))
            log.info("MW550 {0} (UNIT16)".format(rr.registers[50]))
            log.info("MW502 {0} (UNIT16)".format(rr.registers[2]))
            log.info("MW506 {0} (UNIT16)".format(rr.registers[6]))
            # conversione in bit array
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[2:7],endian=Endian.Little)
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
            log.info("MW502 as bits ##########################")
            for idx, b502 in enumerate(bits_502):
                log.info("MW502:X{0} = {1}".format(idx,b502))
            log.info("MW504 as bits ##########################")
            for idx, b504 in enumerate(bits_504):
                log.info("MW504:X{0} = {1}".format(idx,b504))
            log.info("MW506 as bits ##########################")
            for idx, b506 in enumerate(bits_506):
                log.info("MW506:X{0} = {1}".format(idx,b506))
            # lettura %MW512-%MW515 TEMPI
            log.info(u"MW512 Tempo Attività pompa assoluto {0} (UNIT16)".format(rr.registers[12]))
            log.info(u"MW513 Tempo Attività iniettore assoluto {0} (UNIT16)".format(rr.registers[13]))
            log.info(u"MW514 Tempo Attività pompa giornaliero {0} (UNIT16)".format(rr.registers[14]))
            log.info(u"MW515 Tempo Attività iniettore giornaliero {0} (UNIT16)".format(rr.registers[15]))
            # lettura %MW516 PRESSIONE ATTUALE IN USCITA
            log.info(u"MW516 PRESSIONE ATTUALE IN USCITA {0} (UNIT16)".format(rr.registers[16]))
            # lettura portata %MW520	CICLI / MINUTO
            cicli_minuto = rr.registers[20] # può essere 0
            log.info(u"MW520 PORTATA IN CICLI/MINTO IN USCITA {0} (UNIT16), equivalente a {1} LITRI/MINUTO oppure a {2} MC/ORA".format(cicli_minuto, cicli_minuto*liters_cycle,  60.0*cicli_minuto*liters_cycle/1000.0))
            # lettura portata %MF522	LITRI / MINUTO e %MF524 MC / ORA
            decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[22:26],endian=Endian.Little)
            f_522 = decoder.decode_32bit_float()
            f_524 = decoder.decode_32bit_float()
            log.info(u"MF522 PORTATA IN LITRI/MINUTO IN USCITA {0} (FLOAT32), equivalente a MF524 {1} MC/ORA ".format(f_522, f_524))
            if cicli_minuto > 0:
                log.info(u"Volume Cilindro {0} lit".format(f_522/cicli_minuto))
            else:
                pass
            # %MW502:X4 pompa ina llarme FALSE e %MW502:X10 Macchina pronta per comando remoto TRUE
            #if bits_502[4] == False:
            if bits_502[4] == False and bits_502[10] == True: # interruttore invertito NON mi da pompa pronta per comando remoto
                log.info(u"Macchina pronta per comando remoto ###########################")
                # leggo da MW560 a MW562, COMANDO BAR DA REMOTO e COMANDO NUMERO CICLI MINUTO DA REMOTO
                log.info("\tComando bar Remoto 560={0}\tComando Cicli Remoto 562={1}".format(rr.registers[60],rr.registers[62]))
                bExisting = False
                # incremento di 1 se il valore è già impostato

                rr.registers[60] = default_bar
                rr.registers[62] = default_cicli
                """
                if rr.registers[60] > 0:
                    rr.registers[60] += 1
                else:
                    bExisting = False

                # incremento di 1 se il valore è già impostato
                if rr.registers[62] > 0:
                    rr.registers[62] += 1
                else:
                    rr.registers[62] = default_cicli
                    bExisting = False
                """
                # Scrittura registri per impostare valori
                rr.registers[50] += 1
                rq = client.write_registers(starting_register, rr.registers,unit=1)
                if rq.function_code < 0x80:
                    log.info("OK")
                    rr = client.read_holding_registers(starting_register,100,unit=1)
                    if isinstance(rr ,ExceptionResponse):
                        log.error("Errore sul secondo read_holding_registers {0}: {1}".format(starting_register,rr))
                    else:
                        log.info("\t {2}-{3} Comando bar Remoto aggiornato 560={0}\tComando Cicli Remoto aggiornato 562={1}".format(rr.registers[60],rr.registers[62],rr.registers[0],rr.registers[50]))
                        if bExisting:
                            rr.registers[60] -= 1
                            rr.registers[62] -= 1
                            # Scrittura
                            rr.registers[50] += 1
                            rq = client.write_registers(starting_register, rr.registers,unit=1)
                            rr = client.read_holding_registers(starting_register,100,unit=1)
                            log.info("{2}-{3} ristabiliti i valori originali \t560={0}\t562={1} ".format(rr.registers[60],rr.registers[62],rr.registers[0],rr.registers[50]))
                        else:
                            pass
                        # conversione in bit array da 502 a 506
                        decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[2:7],endian=Endian.Little)
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
                        # conversione in bit array da 552
                        decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[52:53],endian=Endian.Little)
                        bits_552 = decoder.decode_bits()
                        bits_552 += decoder.decode_bits()
                        # %MW552:X2 START INIET. DA REMOTO
                        bits_552[2] = True
                        bits_552[3] = False
                        bits_552[14] = True
                        builder = BinaryPayloadBuilder(endian=Endian.Little)
                        # builder.add_bits(bits_502)
                        builder.add_bits(bits_552)
                        reg_552 = builder.to_registers()
                        rr.registers[52:53] = reg_552
                        rr.registers[50] += 1
                        rq = client.write_registers(starting_register, rr.registers,unit=1)
                        log.info("...wait 2 seconds")
                        time.sleep(60)
                        for i in range(3):
                             rr.registers[60] += 5
                             #rr.registers[62] += 5
                             rq = client.write_registers(starting_register, rr.registers,unit=1)
                             log.info("{0}-{1}...wait 60 seconds".format( rr.registers[60], rr.registers[62]))
                             for j in range(60):
                                 rr = client.read_holding_registers(starting_register,100,unit=1)
                                 # lettura %MW516 PRESSIONE ATTUALE IN USCITA
                                 log.info(u"{0} - MW516 PRESSIONE ATTUALE IN USCITA {1} (UNIT16)".format(j,rr.registers[16]))
                                 # lettura portata %MW520	CICLI / MINUTO
                                 cicli_minuto = rr.registers[20] # può essere 0
                                 log.info(u"MW520 PORTATA IN CICLI/MINTO IN USCITA {0} (UNIT16), equivalente a {1} LITRI/MINUTO oppure a {2} MC/ORA".format(cicli_minuto, cicli_minuto*liters_cycle,  60.0*cicli_minuto*liters_cycle/1000.0))
                                 # lettura portata %MF522	LITRI / MINUTO e %MF524 MC / ORA
                                 decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[22:26],endian=Endian.Little)
                                 f_522 = decoder.decode_32bit_float()
                                 f_524 = decoder.decode_32bit_float()
                                 log.info(u"MF522 PORTATA IN LITRI/MINUTO IN USCITA {0} (FLOAT32), equivalente a MF524 {1} MC/ORA ".format(f_522, f_524))
                                 if cicli_minuto > 0:
                                     log.info(u"Volume Cilindro {0} lit".format(f_522/cicli_minuto))
                                 else:
                                     pass
                                 time.sleep(1)
                        rr = client.read_holding_registers(starting_register,100,unit=1)
                        # conversione in bit array da 502 a 506
                        decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[2:7],endian=Endian.Little)
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
                        # conversione in bit array da 552
                        decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[52:53],endian=Endian.Little)
                        bits_552 = decoder.decode_bits()
                        bits_552 += decoder.decode_bits()
                        log.info("{2}-{3} %MW506:X2 => {0} e %MW552:X2 => {1}".format(bits_506[2],bits_552[2],rr.registers[0],rr.registers[50]))
                        log.info("{2}-{3} %MW506:X3 => {0} e %MW552:X3 => {1}".format(bits_506[3],bits_552[3],rr.registers[0],rr.registers[50]))
                        log.info("...wait 10 seconds")
                        time.sleep(10)
                        # %MW552:X3 STOP INIET. DA REMOTO
                        bits_552[2] = False
                        bits_552[3] = True
                        builder = BinaryPayloadBuilder(endian=Endian.Little)
                        builder.add_bits(bits_552)
                        reg_552 = builder.to_registers()
                        rr.registers[52:53] = reg_552
                        rr.registers[50] += 1
                        rq = client.write_registers(starting_register, rr.registers,unit=1)
                        # DOPO STOP
                        log.info("...wait 2 seconds")
                        time.sleep(2)
                        rr = client.read_holding_registers(starting_register,100,unit=1)
                        # conversione in bit array da 502 a 506
                        decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[2:7],endian=Endian.Little)
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
                        # conversione in bit array da 552
                        decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[52:53],endian=Endian.Little)
                        bits_552 = decoder.decode_bits()
                        bits_552 += decoder.decode_bits()
                        log.info("{2}-{3} %MW506:X2 => {0} e %MW552:X2 => {1}".format(bits_506[2],bits_552[2],rr.registers[0],rr.registers[50]))
                        log.info("{2}-{3} %MW506:X3 => {0} e %MW552:X3 => {1}".format(bits_506[3],bits_552[3],rr.registers[0],rr.registers[50]))
                else:
                    log.error("Errore di scrittura sui registri")
            else:
                log.error(u"Impossibile attivare il comando remoto ###########################")
                for idx,b in enumerate(bits_502):
                    log.error("502:X{0} = {1}".format(idx,b))
        else:
            log.error("Errore su registro {0}, valore {1} != {2}".format(test_reg_no,rr.registers[test_reg_no],test_value))
    client.close()
    log.info("Chiusa la connessione Modbus TCP a {0}:{1}".format(host,port))
except ConnectionException as cex:
    log.error("Errore connessione Modbus TCP {1}:{2}. {0}".format(cex,host,port))
