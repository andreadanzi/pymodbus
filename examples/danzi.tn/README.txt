=================================== README

ctest.py is a python script for testing TCP connections on Pumps and Manifolds

To run the test you have to know:
- IP address of the equipment you want to test (eg. 10.243.37.1 for the Manifold #1, 10.243.37.101 for the Pump #1)
- TCP port of the equipment (eg. 502)

Obviously the selected IP address must be reachable from this laptop (eg. try >ping 10.243.37.101)

=========== For testing Pumps, run from a terminal

>cd ~/Documents/test
>python ctest.py -p 502 -i 10.243.37.101 - t P

The expected output is:

Equipment type P connected on 10.243.37.101:502. Connection test passed!
%MW500 = 	2		COUNTER PLC
%MW502:X0 = 	True		Pompa in locale
%MW502:X6 = 	True		Pompa olio on
%MW502:X10 = 	True		Macchina pronta per comando remoto
%MW506:X3 = 	True		STOP INIET. REMOTO PLC
%MW512 = 	1		TEMPO DI ATTIVITA' POMPA
%MW513 = 	1		TEMPO DI ATTIVITA' INIETTORE
%MW514 = 	2		TEMPO DI ATTIVITA' POMPA GIORNALIERO
%MW515 = 	2		TEMPO DI ATTIVITA' INIETTORE GIORNALIERO
%MW516 = 	0		PRESSIONE ATTUALE (BAR)
%MW520 = 	0		PORTATA ATTUALE (CICLI/MIN)
%MW550 = 	2		COUNTER REMOTO
%MW560 = 	2		COMANDO PRESSIONE MAX REMOTO (BAR)
%MW562 = 	2		COMANDO PORTATA MAX REMOTO (CICLI/MIN)
2
Pump register 500 = 2, ok!


=========== For testing Manifolds, run from a terminal

>cd ~/Documents/test
>python ctest.py -p 502 -i 10.243.37.1 - t M

The expected output is:

Equipment type M connected on 10.243.37.1:502. Connection test passed!
Manifold first register value = 20992, OK!
Manifold IP address 10.243.37.1 
	ANA to ENG Pressure parameters: from 4000-20000 to 0-1000
		Pressure: slope=0.00625, intercept=-25.0
	ANA to ENG Flowrate parameters: from 4000-20000 to 0-2000
		Flowrate: slope=0.0125, intercept=-50.0

=========== Options are:

	-i	IP address of the equipment
	-p	TCP port of the equipmnet
	-t	type of the equipment: P for Pumps, M for Manifolds

=========== Log file
	
	inside the current working directory you should find a log file named ctest.log


=========== Default configuration of equipments

Equipment	Prog.	type	IP Address	Port	Serial Number
------------------------------------------------------------------------
MANIFOLD	01	M	10.243.37.1	502	16-43-001
MANIFOLD	02	M	10.243.37.2	502	16-43-002
MANIFOLD	03	M	10.243.37.3	502	16-43-003
MANIFOLD	04	M	10.243.37.4	502	16-43-004
MANIFOLD	05	M	10.243.37.5	502	16-43-005
MANIFOLD	06	M	10.243.37.6	502	16-43-006
MANIFOLD	07	M	10.243.37.7	502	16-43-007
MANIFOLD	08	M	10.243.37.8	502	16-43-008
MANIFOLD	09	M	10.243.37.9	502	16-43-009
MANIFOLD	10	M	10.243.37.10	502	16-43-010
MANIFOLD	11	M	10.243.37.11	502	16-43-011
MANIFOLD	12	M	10.243.37.12	502	16-43-012
MANIFOLD	13	M	10.243.37.13	502	16-43-013
MANIFOLD	14	M	10.243.37.14	502	16-43-014
MANIFOLD	15	M	10.243.37.15	502	16-43-015
MANIFOLD	16	M	10.243.37.16	502	16-43-016
MANIFOLD	17	M	10.243.37.17	502	16-43-017
MANIFOLD	18	M	10.243.37.18	502	16-43-018
MANIFOLD	19	M	10.243.37.19	502	16-43-019
MANIFOLD	20	M	10.243.37.20	502	16-43-020
PUMP		01	P	10.243.37.101	502	07-0001
PUMP		02	P	10.243.37.102	502	07-0002
PUMP		03	P	10.243.37.103	502	07-0003
PUMP		04	P	10.243.37.104	502	07-0004
PUMP		05	P	10.243.37.105	502	07-0005
PUMP		06	P	10.243.37.106	502	07-0006
PUMP		07	P	10.243.37.107	502	07-0007
PUMP		08	P	10.243.37.108	502	07-0008
PUMP		09	P	10.243.37.109	502	07-0009
PUMP		10	P	10.243.37.110	502	07-0010
PUMP		11	P	10.243.37.111	502	07-0011
PUMP		12	P	10.243.37.112	502	07-0012
PUMP		13	P	10.243.37.113	502	07-0013
PUMP		14	P	10.243.37.114	502	07-0014
PUMP		15	P	10.243.37.115	502	07-0015
PUMP		16	P	10.243.37.116	502	07-0016
PUMP		17	P	10.243.37.117	502	07-0017
PUMP		18	P	10.243.37.118	502	07-0018
PUMP		19	P	10.243.37.119	502	07-0019
PUMP		20	P	10.243.37.120	502	07-0020


Examples:

python ctest.py -t M -i 10.243.37.1 -p 502
python ctest.py -t M -i 10.243.37.2 -p 502
python ctest.py -t M -i 10.243.37.3 -p 502
python ctest.py -t M -i 10.243.37.4 -p 502
python ctest.py -t M -i 10.243.37.5 -p 502
python ctest.py -t M -i 10.243.37.6 -p 502
python ctest.py -t M -i 10.243.37.7 -p 502
python ctest.py -t M -i 10.243.37.8 -p 502
python ctest.py -t M -i 10.243.37.9 -p 502
python ctest.py -t M -i 10.243.37.10 -p 502
python ctest.py -t M -i 10.243.37.11 -p 502
python ctest.py -t M -i 10.243.37.12 -p 502
python ctest.py -t M -i 10.243.37.13 -p 502
python ctest.py -t M -i 10.243.37.14 -p 502
python ctest.py -t M -i 10.243.37.15 -p 502
python ctest.py -t M -i 10.243.37.16 -p 502
python ctest.py -t M -i 10.243.37.17 -p 502
python ctest.py -t M -i 10.243.37.18 -p 502
python ctest.py -t M -i 10.243.37.19 -p 502
python ctest.py -t M -i 10.243.37.20 -p 502
python ctest.py -t P -i 10.243.37.101 -p 502
python ctest.py -t P -i 10.243.37.102 -p 502
python ctest.py -t P -i 10.243.37.103 -p 502
python ctest.py -t P -i 10.243.37.104 -p 502
python ctest.py -t P -i 10.243.37.105 -p 502
python ctest.py -t P -i 10.243.37.106 -p 502
python ctest.py -t P -i 10.243.37.107 -p 502
python ctest.py -t P -i 10.243.37.108 -p 502
python ctest.py -t P -i 10.243.37.109 -p 502
python ctest.py -t P -i 10.243.37.110 -p 502
python ctest.py -t P -i 10.243.37.111 -p 502
python ctest.py -t P -i 10.243.37.112 -p 502
python ctest.py -t P -i 10.243.37.113 -p 502
python ctest.py -t P -i 10.243.37.114 -p 502
python ctest.py -t P -i 10.243.37.115 -p 502
python ctest.py -t P -i 10.243.37.116 -p 502
python ctest.py -t P -i 10.243.37.117 -p 502
python ctest.py -t P -i 10.243.37.118 -p 502
python ctest.py -t P -i 10.243.37.119 -p 502
python ctest.py -t P -i 10.243.37.120 -p 502


nmap -sP 10.243.37.*
