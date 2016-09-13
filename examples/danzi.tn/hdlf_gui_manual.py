# -*- coding: utf-8 -*-
"""
Created on Thu Aug 11 11:40:06 2016

@author: andrea
"""

import gi
import csv
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from twisted.internet.task import LoopingCall

from twisted.internet import gtk3reactor
gtk3reactor.install()

from twisted.internet import reactor

import logging, datetime, os, ConfigParser, time
import subprocess, collections
import logging.handlers

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
from pymodbus.constants import Endian

import numpy as np

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

sCurrentWorkingdir = os.getcwd()
sDate = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
export_csv = "hdlf_{0}.csv".format(sDate)
export_csv_path = os.path.join(sCurrentWorkingdir,"out",export_csv)

sCFGName = 'hdlf.cfg'
smtConfig = ConfigParser.RawConfigParser()
cfgItems = smtConfig.read(sCFGName)

log = logging.getLogger()
log.setLevel(logging.INFO)
file_handler = logging.handlers.RotatingFileHandler(export_csv_path, maxBytes=5000000,backupCount=5)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s;%(message)s')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)
log.info("R;p_mA1;p_Eng1;q_mA1;q_Eng1;p_Low1;p_High1;p_EngLow1;p_EngHigh1;q_Low1;q_High1;q_EngLow1;q_EngHigh1;p_AVG;p_Eff;q_AVG;pipeLength;pipeDiam;pipeType;mixType;mixDensity;staticHead;dynamicHeadLosses;p_out;q_out;p_max;q_max;dPOutMax;dPPump;q2;q1;k;fPoutMax")
test_reg_no = 0 # test the expected value (Machine ID, defaukt is 0x5100)
test_value = 20992 # 0x5200 => 20992

# CAVALLETTO 1
manifold_host_1 = '127.0.0.1' # 10.243.37.xx
manifold_port_1 = "5020"  # 502
client_1 = None


low, high = 4000, 20000 # danzi.tn@20160728 current as nanoampere nA - analogic values

# Scale P 
low_p, high_p = 0, 1000 # danzi.tn@20160728 pressure range (P in bar/10)
# Scale Q
low_q, high_q = 0, 2000 # danzi.tn@20160728 flow-rate range (Q in lit/min/10)

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
listP2 = []

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



builder = Gtk.Builder()
builder.add_from_file("hdlf_manual.glade")
builder.get_object("btnOpenFile").set_sensitive(False)

builder.get_object("switchMain").set_sensitive(False)
builder.get_object("switchPumpStatus").set_sensitive(False)

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
a.set_ylim(0, 40)
a.set_xlim(0, x_size)
a2 = a.twinx()

a2.set_ylim(0, 80)
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

    if smtConfig.has_option('HeadLossFactor', 'pipeLength') and smtConfig.has_option('HeadLossFactor', 'mixType'):
        builder.get_object("txtPipeLenght").set_text(smtConfig.get('HeadLossFactor', 'pipeLength'))
        builder.get_object("txtPipeDiam").set_text(smtConfig.get('HeadLossFactor', 'pipeDiam'))
        builder.get_object("txtPipeType").set_text(smtConfig.get('HeadLossFactor', 'pipeType'))
        builder.get_object("txtMixType").set_text(smtConfig.get('HeadLossFactor', 'mixType'))
        builder.get_object("txtMixDensity").set_text(smtConfig.get('HeadLossFactor', 'mixDensity'))
        builder.get_object("txtStaticHead").set_text(smtConfig.get('HeadLossFactor', 'staticHead'))
        builder.get_object("txtQ2").set_text(smtConfig.get('HeadLossFactor', 'Q2'))
        builder.get_object("txtQ1").set_text(smtConfig.get('HeadLossFactor', 'Q1'))
        builder.get_object("txtK").set_text(smtConfig.get('HeadLossFactor', 'K'))


    builder.get_object("txtIP1").set_text(manifold_host_1)
    builder.get_object("txtPort1").set_text(manifold_port_1)
    builder.get_object("txtPortPump").set_text(pump_port)
    builder.get_object("txtIPPump").set_text(pump_host)
    
builder.get_object("txtR").set_text("{}".format(designR))
builder.get_object("txtQmin").set_text("{}".format(designQmin))
builder.get_object("txtRefTime").set_text("{}".format(designRTW))



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
    def __init__(self,a,a2,canvas,loop=None):
        self.loop = loop
        self.ret_m1 = False
        self.afigure = a
        self.afigure2 = a2
        self.canvas = canvas
        self._bufsize = x_size
        self.databuffer_p1 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_p2 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_r = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_q1 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.x = range(x_size)
        self.line_p1, = self.afigure.plot(self.x, self.databuffer_p1,"b-", label='Pg')
        self.line_p2, = self.afigure.plot(self.x, self.databuffer_p2,"-", color='#ffa100', label='Pe')
        self.line_r, = self.afigure.plot(self.x, self.databuffer_r,"r-", label='R')
        self.line_q1, = self.afigure2.plot(self.x, self.databuffer_q1,"m-",  label='Q')

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
        self.treeview2  = builder.get_object("treeview2")
        self.p_count = 0
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Name", renderer, text=0)
        self.treeview2.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Description", renderer, text=1)
        self.treeview2.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Value", renderer, text=2)
        self.treeview2.append_column(column)

        self.adjustPMax = builder.get_object("adjustment1")
        self.adjustQMax = builder.get_object("adjustment2")
        self.chkPAna = builder.get_object("chkPAna")
        self.txtDHLF = builder.get_object("txtDHLF")
        self.btnAnalyze = builder.get_object("btnAnalyze")
        self.txtRefPressure = builder.get_object("txtR")
        self.btnAnalyze.set_sensitive(False)
        self.time = datetime.datetime.utcnow()
        self.lastPe = collections.deque(maxlen=designRTW*60)
        self.lastPg = collections.deque(maxlen=designRTW*60)
        self.lastQ = collections.deque(maxlen=designRTW*60)
        self.txtQ2 = builder.get_object("txtQ2")
        self.txtQ1 = builder.get_object("txtQ1")
        self.txtK = builder.get_object("txtK")
        self.txtPoutMax = builder.get_object("txtPoutMax")
        self.lblOK = builder.get_object("lblOK")
        self.hdlf_q2 = 0
        self.hdlf_q1 = 0
        self.hdlf_k = 0
        
        self.designQmin = 0.
        


    def logging_data(self, a):
        self.send_parity()
        t1=datetime.datetime.utcnow()
        dt_seconds = (t1-self.time).seconds
        builder.get_object("levelbar1").set_value(len(listP1)%60+1)
        client_1 = a[0]
        client_p = a[8]
        txtPout = a[9]
        txtQout = a[10]
        aIN1 = a[1]
        aIN2 = a[2]
        aIN1ENG = a[3]
        aIN2ENG = a[4]
        aIN12 = a[5]
        aIN22 = a[6]
        aIN1ENG2 = a[7]
        strR = self.txtRefPressure.get_text()
        if strR.isdigit():
            self.pR = int(strR)
        else:
            self.pR = 10
            self.txtRefPressure.set_text("10")


        strR = builder.get_object("txtPipeLenght").get_text()
        if strR.isdigit():
            self.pipeLength = int(strR)
        else:
            builder.get_object("txtPipeLenght").set_text(str(self.pipeLength))
        
        
        self.hdlf_q2 = float(builder.get_object("txtQ2").get_text())
        self.hdlf_q1 = float(builder.get_object("txtQ1").get_text())
        self.hdlf_k = float(builder.get_object("txtK").get_text())

        strR = builder.get_object("txtStaticHead").get_text()
        try:
            self.staticHead = float(strR)
        except ValueError:
            builder.get_object("txtStaticHead").set_text(str(self.staticHead))
        
        
        rr1 = client_1.read_holding_registers(0,48)
        if rr1.registers[test_reg_no] == test_value:
            p_mA1 = rr1.registers[4-1]# AIN1 pressione in mA in posizione 4
            p_Eng1 = int(pEngFunc(p_mA1))
            # AIN2 portata in mA in posizione 6
            q_mA1 = rr1.registers[6-1]
            q_Eng1 = int(qEngFunc(q_mA1))            
            rr1_103 = client_1.read_holding_registers(103,10)
            reg104_1 = tuple(rr1_103.registers )
            
            
            p_mA2 = 0 # rr2.registers[4-1]# AIN1 pressione in mA in posizione 4
            p_Eng2 = 0 # rr2.registers[5-1]
            # AIN2 portata in mA in posizione 6
            q_mA2 = 0 # rr2.registers[6-1]
            if p_mA1 <= 4000:
                p_mA1 = 0
                p_Eng1 = 0
            if q_mA1 <= 4000:
                q_mA1 = 0
                q_Eng1 = 0

      
            hdlf = (self.hdlf_q2, self.hdlf_q1,self.hdlf_k)
            self.pDHL = phdlf( q_Eng1/10. ,self.pipeLength, hdlf )
            p_Eng2 = p_Eng1 - 10.*self.pDHL + 10.*self.staticHead
            
            self.lastQ.append(q_Eng1/10.)
            self.lastPe.append(p_Eng2/10.)
            self.lastPg.append(p_Eng1/10.)            
            if len(self.lastPe) == self.lastPe.maxlen:
                p_mA2 = np.mean(self.lastPe)
                q_mA2 = np.mean(self.lastQ)
                pRate = p_mA2/self.pR
                if q_mA2 <= self.designQmin and p_mA2 >= self.pR:
                    self.lblOK.set_label("OK")
                else:
                    self.lblOK.set_label("P<R ({0:.2f})".format(pRate))            
                
            self.txtDHLF.set_text("{0:.2f}".format(-self.pDHL))
            self.databuffer_p1.append( p_Eng1/10. )
            self.line_p1.set_ydata(self.databuffer_p1)
            self.databuffer_p2.append( p_Eng2/10. )
            self.line_p2.set_ydata(self.databuffer_p2)
            self.databuffer_r.append( self.pR )
            self.line_r.set_ydata(self.databuffer_r)


            self.databuffer_q1.append( q_Eng1/10. )
            self.line_q1.set_ydata(self.databuffer_q1)

            self.afigure.relim()
            self.afigure.autoscale_view(False, False, True)
            self.afigure2.relim()
            self.afigure2.autoscale_view(False, False, True)
            self.canvas.draw()

            listP1.append(p_Eng1/10.)
            listP2.append(p_Eng2/10.)
            aIN1.set_text(str(p_mA1))
            aIN2.set_text(str(q_mA1))
            aIN1ENG.set_text("{0} bar".format(p_Eng1/10.))
            aIN2ENG.set_text("{0} lit/min".format(q_Eng1/10.))
            
            aIN12.set_text("{0:.2f} bar".format(p_mA2))
            aIN22.set_text("{0:.2f} lit/min".format(q_mA2))
            
            aIN1ENG2.set_text("{0} bar".format(p_Eng2/10.))
            # INIETTORE
            rr_p = client_p.read_holding_registers(500,100,unit=1)
            txtPout.set_text("{0} bar".format(rr_p.registers[16]))


            fPoutMax = self.pR + rr_p.registers[16] - p_Eng2/10.            
            self.txtPoutMax.set_text("{0}".format(int(fPoutMax)))
            txtQout.set_text("{0} c/min {1:.2f} l/min".format(rr_p.registers[20], litCiclo*rr_p.registers[20] ))
            self.pmax = rr_p.registers[60]
            if self.chkPAna.get_active():
                self.qmax = rr_p.registers[64]
                builder.get_object("txtQmax").set_text("{0} V".format(self.qmax))
            else:
                self.qmax = rr_p.registers[62]
                builder.get_object("txtQmax").set_text("{0} c/min {1:.2f} l/min".format(self.qmax, litCiclo*self.qmax))
            # self.qVmax = rr_p.registers[64]
            builder.get_object("txtPmax").set_text("{0} bar".format(rr_p.registers[60]))
            # print "P: {0}->{1} \tdP = {4} \t\tQ: {2}->{3} \tn={5} \tavg P1 {6:.2f}({7:.2f}) P2 {8:.2f}({9:.2f})".format(p_Eng1/10.,p_Eng2/10.,q_Eng1/10.,q_Eng2/10.,(p_Eng1-p_Eng2)/10., len(listP1), np.mean(listP1),np.std(listP1),np.mean(listP2),np.std(listP2) )
            if self.blogFile:
                self.oneLogged = True
                # TODO btnLog set label
                # time now - before
                builder.get_object("btnLog").set_label("{0}".format(datetime.timedelta(seconds =dt_seconds)))
                log.info("%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d;%f;%f;%s;%s;%f;%f;%f;%d;%d;%d;%d;%f;%f;%f;%f;%f;%f" % (self.pR, p_mA1, p_Eng1, q_mA1, q_Eng1,reg104_1[0] ,reg104_1[1] ,reg104_1[2] , reg104_1[3],reg104_1[6] ,reg104_1[7] ,reg104_1[8] , reg104_1[9],p_mA2, p_Eng2, q_mA2,  self.pipeLength, self.pipeDiam,self.pipeType,self.mixType,self.mixDensity,self.staticHead,self.pDHL, rr_p.registers[16],rr_p.registers[20],self.pmax,self.qmax, self.pmax-rr_p.registers[16], rr_p.registers[16]- p_Eng1/10. , hdlf[0], hdlf[1], hdlf[2],fPoutMax))
        else:
            print "error on test data {0} vs {1} or {0} vs {2}".format(test_value,rr1.registers[test_reg_no],rr2.registers[test_reg_no])


    def onDeleteWindow(self, *args):
        Gtk.main_quit(*args)

    def testConnection1(self, button):
        lblTest1 = builder.get_object("lblTest1")
        manifold_host_1 = builder.get_object("txtIP1").get_text()
        manifold_port_1 = int(builder.get_object("txtPort1").get_text())
        client_1 = ModbusClient(manifold_host_1, port=manifold_port_1)
        self.ret_m1=client_1.connect()
        lblTest1.set_text(str(self.ret_m1))
        if not smtConfig.has_section('Manifold_1'):
            smtConfig.add_section('Manifold_1')
        if self.ret_m1:
            builder.get_object("switchMain").set_sensitive(True)
            smtConfig.set('Manifold_1', 'host', manifold_host_1)
            smtConfig.set('Manifold_1', 'port', manifold_port_1)
            with open(sCFGName, 'wb') as configfile:
                smtConfig.write(configfile)
        client_1.close()


    def on_btnConnectPump_clicked(self, button):
        lblTestPump = builder.get_object("lblTestPump")
        pump_host = builder.get_object("txtIPPump").get_text()
        pump_port = int(builder.get_object("txtPortPump").get_text())
        self.client_p = ModbusClient(pump_host, port=pump_port)
        self.ret_p=self.client_p.connect()
        lblTestPump.set_text(str(self.ret_p))
        if not smtConfig.has_section('Pump'):
            smtConfig.add_section('Pump')
        if self.ret_p:
            self.checkPump(self.client_p)
            smtConfig.set('Pump', 'host', pump_host)
            smtConfig.set('Pump', 'port', pump_port)
            with open(sCFGName, 'wb') as configfile:
                smtConfig.write(configfile)
        self.client_p.close()


    def checkPump(self,client_p):
        rr = client_p.read_holding_registers(500,100,unit=1)
        # conversione in bit array da 552
        decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[52:53],endian=Endian.Little)
        bits_552 = decoder.decode_bits()
        bits_552 += decoder.decode_bits()
        bits_552[10] = True
        b_builder = BinaryPayloadBuilder(endian=Endian.Little)
        b_builder.add_bits(bits_552)
        reg_552 = b_builder.to_registers()
        rr.registers[52:53] = reg_552
        for it in range(10):
            self.p_count += 1
            rr.registers[50] = self.p_count
            rq = client_p.write_registers(500, rr.registers,unit=1)
            if rq.function_code < 0x80:
                rr_p = client_p.read_holding_registers(500,100,unit=1)
                if len(rr_p.registers)==100 and rr_p.registers[0]==self.p_count:
                    decoder = BinaryPayloadDecoder.fromRegisters(rr_p.registers[2:7],endian=Endian.Little)
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
                    if bits_502[7]:
                        builder.get_object("switchPumpStatus").set_active(True)
                    else:
                        builder.get_object("switchPumpStatus").set_active(False)

                    if bits_502[4] == False and bits_502[10] == True:
                        builder.get_object("switchPumpStatus").set_sensitive(True)
                    else:
                        builder.get_object("switchPumpStatus").set_sensitive(False)
                else:
                    print "errore checkPump %d" % self.p_count
        bits_552[10] = False
        print str(bits_552)
        b_builder = BinaryPayloadBuilder(endian=Endian.Little)
        b_builder.add_bits(bits_552)
        reg_552_2 = b_builder.to_registers()
        rr.registers[52:53] = reg_552_2
        rq = client_p.write_registers(500, rr.registers,unit=1)
        if rq.function_code < 0x80:
            pass
        else:
            print "checkPump terminato con scrittura KO"

    def on_btnOpenFile_clicked(self,button):
        #os.system()
        subprocess.call(["libreoffice",export_csv_path])


    def on_btnGetPump_clicked(self,button):
        self.adjustPMax.set_value(float(self.pmax) )
        self.adjustQMax.set_value(float(self.qmax))


    def send_parity(self):
        self.p_count += 1
        rr_p = self.client_p.write_registers(550,self.p_count,unit=1)

    def on_btnSetPump_clicked(self,button):
        rr_p = self.client_p.read_holding_registers(500,100,unit=1)
        decoder = BinaryPayloadDecoder.fromRegisters(rr_p.registers[52:53],endian=Endian.Little)
        bits_552 = decoder.decode_bits()
        bits_552 += decoder.decode_bits()
        self.pmax = self.adjustPMax.get_value()
        self.qmax = self.adjustQMax.get_value()
        self.p_count += 1
        rr_p.registers[50] = self.p_count
        rr_p.registers[60] = int(self.pmax)
        if self.chkPAna.get_active():
            rr_p.registers[64] = int(self.qmax)
            # TODO rr_p.registers[62] = equivalente mappato
            bits_552[12] = True
        else:
            rr_p.registers[62] = int(self.qmax)
            rr_p.registers[64] = cicli_volt[int(self.qmax)]
            bits_552[12] = False
        b_builder = BinaryPayloadBuilder(endian=Endian.Little)
        # builder.add_bits(bits_502)
        b_builder.add_bits(bits_552)
        reg_552 = b_builder.to_registers()
        rr_p.registers[52:53] = reg_552
        rr_p = self.client_p.write_registers(500,rr_p.registers,unit=1)


    def on_btnOff_clicked(self,button):
        print("Closing application")
        Gtk.main_quit()

    def on_btnLog_toggled(self,button):
        if button.get_active():
            self.time = datetime.datetime.utcnow()
                
            self.blogFile = True
        else:
            self.blogFile = False
            builder.get_object("btnLog").set_label("Log Data")


    def readDataSetupConfig(self):
        self.pipeLength = float(builder.get_object("txtPipeLenght").get_text())
        self.pipeDiam  =  float(builder.get_object("txtPipeDiam").get_text())
        self.pipeType  = builder.get_object("txtPipeType").get_text()
        self.mixType  = builder.get_object("txtMixType").get_text()
        self.mixDensity  =  float(builder.get_object("txtMixDensity").get_text())
        self.staticHead = float(builder.get_object("txtStaticHead").get_text())
        self.hdlf_q2 = float(builder.get_object("txtQ2").get_text())
        self.hdlf_q1 = float(builder.get_object("txtQ1").get_text())
        self.hdlf_k = float(builder.get_object("txtK").get_text())
        self.pR = int(builder.get_object("txtR").get_text())
        self.designQmin = int(builder.get_object("txtQmin").get_text())
        designRTW = int(builder.get_object("txtRefTime").get_text())
        
        if designRTW*60 != self.lastPe.maxlen:
            print "resize RTW from {0} to {1}".format(self.lastPe.maxlen, designRTW*60)
            self.lastPe = collections.deque(self.lastPe, maxlen=designRTW*60)
            self.lastPg = collections.deque(self.lastPg, maxlen=designRTW*60)
            self.lastQ = collections.deque(self.lastQ, maxlen=designRTW*60)

        if not smtConfig.has_section('HeadLossFactor'):
            smtConfig.add_section('HeadLossFactor')
        smtConfig.set('HeadLossFactor', 'pipeLength', self.pipeLength)
        smtConfig.set('HeadLossFactor', 'pipeDiam', self.pipeDiam)
        smtConfig.set('HeadLossFactor', 'pipeType', self.pipeType)
        smtConfig.set('HeadLossFactor', 'mixType', self.mixType)
        smtConfig.set('HeadLossFactor', 'mixDensity', self.mixDensity)
        smtConfig.set('HeadLossFactor', 'staticHead', self.staticHead)
        smtConfig.set('HeadLossFactor', 'Q2', self.hdlf_q2)
        smtConfig.set('HeadLossFactor', 'Q1', self.hdlf_q1)
        smtConfig.set('HeadLossFactor', 'K', self.hdlf_k)
        
        
        if not smtConfig.has_section('Design'):
            smtConfig.add_section('Design')
        smtConfig.set('Design', 'R', self.pR)
        smtConfig.set('Design', 'Qmin', self.designQmin)
        smtConfig.set('Design', 'RTW', designRTW)        
        
        with open(sCFGName, 'wb') as configfile:
            smtConfig.write(configfile)

    def on_switchPumpStatus_state_set(self, switch,gparam):
        self.ret_p=self.client_p.connect()
        rr = self.client_p.read_holding_registers(500,100,unit=1)
        # conversione in bit array da 552
        decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[52:53],endian=Endian.Little)
        bits_552 = decoder.decode_bits()
        bits_552 += decoder.decode_bits()

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
        bSendCommand = False
        if switch.get_active():
            # %MW552:X2 START INIET. DA REMOTO
            bSendCommand = not bits_502[7]
            bits_552[2] = True
            bits_552[3] = False
            bits_552[14] = True
        else:
            # %MW552:X2 STOP INIET. DA REMOTO
            bSendCommand = bits_502[7]
            bits_552[2] = False
            bits_552[3] = True
            bits_552[14] = False
        builder = BinaryPayloadBuilder(endian=Endian.Little)
        # builder.add_bits(bits_502)
        builder.add_bits(bits_552)
        reg_552 = builder.to_registers()
        rr.registers[52:53] = reg_552
        self.p_count += 1
        rr.registers[50] = self.p_count
        if bSendCommand:
            self.client_p.write_registers(500, rr.registers,unit=1)
            if bits_552[2]:
                bits_552[2] = False
                builder = BinaryPayloadBuilder(endian=Endian.Little)
                # builder.add_bits(bits_502)
                builder.add_bits(bits_552)
                reg_552 = builder.to_registers()
                self.client_p.write_register(552, reg_552[0])
                print "pulsante rilasciato"

        self.client_p.close()

    def on_btnShow_clicked(self,button):
        # show dlgRegistries
        self.lstDialog = builder.get_object("dlgRegistries")
        self.liststore = builder.get_object("liststore1")
        if self.ret_p:
            self.liststore.clear()
            rr = self.client_p.read_holding_registers(500,100,unit=1)
            for idx in [0,2,4,6,12,13,14,15,16,20,50,52,60,62,64]:
                if idx in (2,4,6,52):
                    decoder = BinaryPayloadDecoder.fromRegisters(rr.registers[idx:idx+1],endian=Endian.Little)
                    bits = decoder.decode_bits()
                    bits += decoder.decode_bits()
                    for ib, b in enumerate(bits):
                        if b:
                            sCode = "%MW5{0:02d}:X{1}".format(idx,ib)
                            self.liststore.append([sCode,reg_descr[sCode], str( b ) ])
                else:
                    sCode = "%MW5{0:02d}".format(idx)
                    self.liststore.append([sCode, reg_descr[sCode], str( rr.registers[idx]) ])


        response = self.lstDialog.run()

        self.lstDialog.hide()

    def on_btnOk_clicked(self,button):
        self.lstDialog.close()



    def on_btnAnalyze_clicked(self,button):
        with open(export_csv_path, 'rb') as csvfile:
            template_vars = {}
            csv_reader = csv.DictReader(csvfile, delimiter=';')
            csv_list = list(csv_reader)
            data = [ np.asarray([row["q_Eng1"],row["dPManifold"],row["q_out"],row["dPPump"] , row["p_Eng1"],row["p_Eng2"]], dtype=np.float64)  for row in csv_list]
            x1 = [d[0]/10. for d in data]
            y1 = [d[1]/10. for d in data]
            x2 = [d[2]*litCiclo for d in data]
            y2 = [d[3] for d in data]
            p1 = [d[4]/10. for d in data]
            p2 = [d[5]/10. for d in data]
            dP = [d[4]/10. - d[5]/10. for d in data]
            # The solution minimizes the squared error
            fit1_1, res1_1, _, _, _ =  np.polyfit(x1, y1,1,full=True)
            fit1_2, res1_2, _, _, _ =  np.polyfit(x1, y1,2,full=True)
            fit2_1, res2_1, _, _, _ =  np.polyfit(x2, y2,1,full=True)
            fit2_2, res2_2, _, _, _ =  np.polyfit(x2, y2,2,full=True)
            p_func_fit1_1 = np.poly1d(fit1_1)
            p_func_fit1_2 = np.poly1d(fit1_2)
            p_func_fit2_1 = np.poly1d(fit2_1)
            p_func_fit2_2 = np.poly1d(fit2_2)
            xp = np.linspace(np.min(x1), np.max(x1), 100)
            fig = plt.figure(figsize=(16, 9), dpi=100)
            plt.plot(x1, y1, 'b.', label='Samples')
            plt.plot(xp, p_func_fit1_1(xp), 'r--', label="Linear (e={0:.3f})".format(res1_1[0]))
            plt.plot(xp, p_func_fit1_2(xp), 'g-', label="Curved (e={0:.3f})".format(res1_2[0]))
            plt.xlabel('Flow Rate (lit/min)')
            plt.ylabel('Pressure (bar)')
            #plt.legend()
            plt.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3, ncol=3, mode="expand", borderaxespad=0.)
            plt.grid(True)
            tex1 = r'$%.3fx^{2}%+.3fx%+.3f$' % tuple(fit1_2)
            plt.text(int(np.min(x1)),np.max(y1)*0.9, tex1, fontsize=16, va='bottom', color="g")

            template_vars["fit1_1"] = tuple(fit1_1)
            template_vars["fit1_2"] = tuple(fit1_2)
            template_vars["res1_1"] = res1_1
            template_vars["res1_2"] = res1_2


            imagefname = "hflf_1_{0}.png".format(sDate)
            imagefpath = os.path.join(sCurrentWorkingdir,"out",imagefname)
            template_vars["hflf_1"] = imagefpath
            plt.savefig(imagefpath,format="png", bbox_inches='tight', pad_inches=0)
            plt.close(fig)

            xp = np.linspace(np.min(x2), np.max(x2), 100)
            fig = plt.figure(figsize=(16, 9), dpi=100)
            plt.plot(x2, y2, 'b.', label='Samples')
            plt.plot(xp, p_func_fit2_1(xp), 'r--', label='Linear model (e={0:.3f})'.format(res2_1[0]))
            plt.plot(xp, p_func_fit2_2(xp), 'g-', label='Curved model (e={0:.3f})'.format(res2_2[0]))
            plt.xlabel('Flow Rate (lit/min)')
            plt.ylabel('Pressure (bar)')
            plt.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3, ncol=3, mode="expand", borderaxespad=0.)
            plt.grid(True)
            tex1 = r'$%.3fx^{2}%+.3fx%+.3f$' % tuple(fit2_2)
            plt.text(int(np.min(x2)),np.max(y2)*0.9, tex1, fontsize=16, va='bottom', color="g")


            imagefname = "hflf_2_{0}.png".format(sDate)
            imagefpath = os.path.join(sCurrentWorkingdir,"out",imagefname)
            template_vars["hflf_2"] = imagefpath
            plt.savefig(imagefpath,format="png", bbox_inches='tight', pad_inches=0)
            plt.close(fig)

            # andamento pressione portata nel tempo
            fig = plt.figure(figsize=(16, 9), dpi=100)
            t = np.arange(len(p1))
            a = fig.add_subplot(212)
            a.grid(True)

            for tick in a.xaxis.get_major_ticks():
                tick.label.set_fontsize(10)
            for tick in a.yaxis.get_major_ticks():
                tick.label.set_fontsize(10)

            a.set_xlabel('Time (seconds)')
            #a.set_ylim(np.min(dP)-2, np.max(dP)+2)
            a.set_ylim(np.min(p1)-2, np.max(p1)+2)
            a.set_xlim(0, len(t)+1)

            a.plot(t, p1, 'bo-', label='P1')
            a.plot(t, p2, 'ro-', label='P2')
            a.set_ylabel('Pressure (P bar)', fontsize=10)
            a.legend(loc=2, ncol=2, fontsize=10)
            a2 = fig.add_subplot(211)
            a2.grid(True)

            for tick in a2.xaxis.get_major_ticks():
                tick.label.set_fontsize(10)

            for tick in a2.yaxis.get_major_ticks():
                tick.label.set_fontsize(10)

            a2.set_xlabel('Time (seconds)')
            a2.set_ylabel('Flow rate (Q lit/min)', fontsize=10)
            a2.set_ylim(np.min(x1)-2, np.max(x1)+2)
            a2.set_xlim(0, len(t)+1)
            #a.plot(t, dP, 'r-', label='dP')
            a2.plot(t, x1, 'go-', label='Q')
            a2.legend(loc=2, ncol=2, fontsize=10)

            template_vars["t_items"] = list(t)
            template_vars["q_items"] = list(x1)
            template_vars["p1_items"] = list(p1)
            template_vars["p2_items"] = list(p2)
            template_vars["dp_items"] = list(dP)
            template_vars["pipeLength"] = self.pipeLength
            template_vars["pipeDiam"] = self.pipeDiam
            template_vars["pipeType"] = self.pipeType
            template_vars["mixType"] = self.mixType
            template_vars["mixDensity"] = self.mixDensity


            imagefname = "time_{0}.png".format(sDate)
            imagefpath = os.path.join(sCurrentWorkingdir,"out",imagefname)
            template_vars["time"] = imagefpath
            plt.savefig(imagefpath,format="png", bbox_inches='tight', pad_inches=0)
            plt.close(fig)
            template_vars["issue_date"] = datetime.datetime.utcnow().strftime("%Y.%m.%d %H:%M:%S")

            env = Environment(loader=FileSystemLoader('.'))
            templateFile = "hdlf_template.html"
            templateFilePath = os.path.join(sCurrentWorkingdir,"out",templateFile)
            template = env.get_template(templateFile)
            html_out = template.render(template_vars)

            pdffname = "hdlf_{0}.pdf".format(sDate)
            pdfpath = os.path.join(sCurrentWorkingdir,"out",pdffname)
            HTML(string=html_out).write_pdf(pdfpath, stylesheets=["typography.css","grid.css"])


    def on_switchMain_activate(self, switch,gparam):
        if switch.get_active():
            self.client_1 = ModbusClient(manifold_host_1, port=manifold_port_1)
            self.client_p = ModbusClient(pump_host, port=pump_port)
            self.client_1.connect()
            self.client_p.connect()
            self.readDataSetupConfig()
            time.sleep(2)
            print "start connection"
            time_delay = 1 # 1 seconds delay
            self.loop = LoopingCall(f=self.logging_data, a=(self.client_1, builder.get_object("txtAIN1"),builder.get_object("txtAIN2"),builder.get_object("txtAIN1ENG"),builder.get_object("txtAIN2ENG"),builder.get_object("txtAIN12"),builder.get_object("txtAIN22"),builder.get_object("txtAIN1ENG2"),self.client_p,builder.get_object("txtPout"),builder.get_object("txtQout")))
            self.loop.start(time_delay, now=False) # initially delay by time
            builder.get_object("btnOpenFile").set_sensitive(False)
            builder.get_object("btnOff").set_sensitive(False)
            self.btnAnalyze.set_sensitive(False)
            # self.ani = animation.FuncAnimation(self.figure, self.update_plot, interval = 1000)
        else:
            self.loop.stop()
            time.sleep(1)
            self.client_1.close()
            self.client_p.close()
            print "stop connection"
            time.sleep(2)
            builder.get_object("txtFilePath").set_text(export_csv_path)
            builder.get_object("btnOpenFile").set_sensitive(True)
            builder.get_object("btnOff").set_sensitive(True)
            if self.oneLogged:
                self.btnAnalyze.set_sensitive(True)



builder.connect_signals(Handler(a,a2,canvas))
window = builder.get_object("windowMain")
window.show_all()
reactor.run()
# Gtk.main()
