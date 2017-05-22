# -*- coding: utf-8 -*-
"""
Created on Thu Aug 11 11:40:06 2016

@author: andrea

danzi.tn@20161114 sampling 1/10 
"""

import gi
import csv
import logging, datetime, os, ConfigParser, time
import subprocess, collections
import logging.handlers
import matplotlib.pyplot as plt
import numpy as np

from pymongo import MongoClient
from pymongo import errors as pyErrors

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from pymodbus.client.sync import ModbusTcpClient as ModbusClient
from twisted.internet.task import LoopingCall
from twisted.internet import gtk3reactor
gtk3reactor.install()
from twisted.internet import reactor
from matplotlib.figure import Figure
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
from pymodbus.constants import Endian


a_low=4000
a_high=20000
p_low=0
p_high=1000
q_low=0
q_high=2000

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

sCurrentWorkingdir = os.getcwd()

sCFGName = 'test_gui.cfg'
smtConfig = ConfigParser.RawConfigParser()
cfgItems = smtConfig.read(sCFGName)


logApp = logging.getLogger()
logApp.setLevel(logging.INFO)

output_folder = os.path.join(sCurrentWorkingdir,"out")
logAppFile = os.path.join(sCurrentWorkingdir,"test_gui.log")         
file_handler = logging.handlers.RotatingFileHandler(logAppFile, maxBytes=5000000,backupCount=5)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logApp.addHandler(file_handler)
logApp.debug("HDLF GUI STARTED")

log = logging.getLogger("csv")
log.setLevel(logging.INFO)
test_reg_no = 0 # test the expected value (Machine ID, defaukt is 0x5100)
test_value_1 = smtConfig.getint('Manifold_1', 'id1')
test_value_2 = smtConfig.getint('Manifold_1', 'id2')

# CAVALLETTO 1
manifold_host_1 = '127.0.0.1' # 10.243.37.xx
manifold_port_1 = "5020"  # 502



stdDev = 0.1
litCiclo = 2.464

builder = Gtk.Builder()
builder.add_from_file("test_gui.glade")
builder.get_object("btnOpenFile").set_sensitive(False)

builder.get_object("switchMain").set_sensitive(False)
builder.get_object("switchPumpStatus").set_sensitive(False)
builder.get_object("btnShow").set_sensitive(False)

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
a3 = a.twinx()
a2.spines["right"].set_position(("axes", 1.2))

a2.set_ylim(-10, 80)
a3.set_ylim(-10, 80)



a2.set_ylabel('Flow rate (Q lit/min)')
a3.set_ylabel('Eng Values')
a.set_ylabel('Pump Out: P (bar) and Q (lit/min)')


scrolledwindow1.set_border_width(5)
samples_no = 1
canvas = FigureCanvas(f)  # a Gtk.DrawingArea
canvas.set_size_request(800, 450)
scrolledwindow1.add_with_viewport(canvas)
canvas.show()
if len(cfgItems) > 0:
    samples_no = smtConfig.getint('General', 'samples_no')
    if smtConfig.has_option('Output', 'folder'):
        output_folder = smtConfig.get('Output', 'folder')    
    if smtConfig.has_option('Manifold_1', 'host') and smtConfig.has_option('Manifold_1', 'port'):
        manifold_host_1 = smtConfig.get('Manifold_1', 'host')
        manifold_port_1 = smtConfig.get('Manifold_1', 'port')   
        a_low= smtConfig.getint('Manifold_1', 'low')
        a_high=smtConfig.getint('Manifold_1', 'high')
        p_low=smtConfig.getint('Manifold_1', 'p_low')
        p_high=smtConfig.getint('Manifold_1', 'p_high')
        q_low=smtConfig.getint('Manifold_1', 'q_low')
        q_high=smtConfig.getint('Manifold_1', 'q_high')
        

    if smtConfig.has_option('Pump', 'host') and smtConfig.has_option('Pump', 'port'):
        pump_host = smtConfig.get('Pump', 'host')
        pump_port = smtConfig.get('Pump', 'port')

    if smtConfig.has_option('HeadLossFactor', 'pipeLength') and smtConfig.has_option('HeadLossFactor', 'mixType'):
        builder.get_object("txtPipeLenght").set_text(smtConfig.get('HeadLossFactor', 'pipeLength'))
        builder.get_object("txtPipeDiam").set_text(smtConfig.get('HeadLossFactor', 'pipeDiam'))
        builder.get_object("txtPipeType").set_text(smtConfig.get('HeadLossFactor', 'pipeType'))
        builder.get_object("txtMixType").set_text(smtConfig.get('HeadLossFactor', 'mixType'))
        builder.get_object("txtMixDensity").set_text(smtConfig.get('HeadLossFactor', 'mixDensity'))
        builder.get_object("txtStaticHead").set_text(smtConfig.get('HeadLossFactor', 'staticHead'))

    builder.get_object("txtIP1").set_text(manifold_host_1)
    builder.get_object("txtPort1").set_text(manifold_port_1)
    builder.get_object("txtPortPump").set_text(pump_port)
    builder.get_object("txtIPPump").set_text(pump_host)



builder.get_object("txtOutFolder").set_text( output_folder)
reg_descr = {"%MW502:X0":"Local control",
             "%MW502:X1":"Remote control",
             "%MW502:X2":"ND",
             "%MW502:X3":"ND",
             "%MW502:X4":"Pump alarm",
             "%MW502:X5":"ND",
             "%MW502:X6":"Oil Pupm on",
             "%MW502:X7":"Running Injector",
             "%MW502:X8":"ND",
             "%MW502:X9":"ND",
             "%MW502:X10":"Ready for remote control",
             "%MW502:X11":"ND",
             "%MW502:X12":"ND",
             "%MW502:X13":"ND",
             "%MW502:X14":"ND",
             "%MW502:X15":"ND",
             "%MW504:X0":"All_Max_Pressure",
             "%MW504:X1":"All_Red_Button",
             "%MW504:X2":"All_Thermic_Pump",
             "%MW504:X3":"All_Thermic_Cooler1",
             "%MW504:X4":"All_OilLevel",
             "%MW504:X5":"All_Pressure_Transaducer",
             "%MW504:X6":"All_PLC Configuration",
             "%MW504:X7":"All_Battery",
             "%MW504:X8":"All_Thermic_Cooler2",
             "%MW504:X9":"All_Thernic Recycle",
             "%MW504:X10":"All_MixerTemperature",
             "%MW504:X11":"ND",
             "%MW504:X12":"ND",
             "%MW504:X13":"ND",
             "%MW504:X14":"ND",
             "%MW504:X15":"ND",
             "%MW506:X0":"START REMOTE PUMP PLC",
             "%MW506:X1":"STOP REMOTE PUMP PLC",
             "%MW506:X2":"START REMOTE Injector PLC",
             "%MW506:X3":"STOP REMOTE Injector PLC",
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
             "%MW506:X14":"RESET COUNTER (DAYLY) PLC",
             "%MW506:X15":"RESET COUNTER PLC",
             "%MW512": "COUNTER PUMP",
             "%MW513": "COUNTER Injector",
             "%MW514": "COUNTER PUM (DAYLY)",
             "%MW515": "COUNTER Injector (DAYLY)",
             "%MW516": "P OUT (BAR)",
             "%MW520": "Q OUT (CYCLES/MIN)",
             "%MW500": "COUNTER PLC",
             "%MW550": "COUNTER REMOTE",
             "%MW560": "P MAX (BAR)",
             "%MW562": "Q MAX (CYCLES/MIN)",
             "%MW552:X0":"START REMOTE PUMP",
             "%MW552:X1":"STOP REMOTE PUMP",
             "%MW552:X2":"START REMOTE Injector",
             "%MW552:X3":"STOP REMOTE Injector",
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
             "%MW552:X14":"RESET COUNTER (DAYLY) REMOTE",
             "%MW552:X15":"RESET COUNTER REMOTE"}




class Handler(object):
    def __init__(self,a,a2,canvas, samples_no=1):     
        self.txtCommentBuffer = builder.get_object("txtCommentBuffer")
        self.dlgComments = builder.get_object("dlgComments")
        self.samples_no = samples_no
        self.loop_no = 0
        self.volume = 0
        self.elapsed = 0
        self.lastTick = None
        self.thisTick = None        
        self.loop = None
        self.listP1 = []
        self.reg104_1 = None
        self.low1, self.high1 = a_low, a_high # danzi.tn@20160728 current as nanoampere nA - analogic values
        self.low2, self.high2 = a_low, a_high # danzi.tn@20160728 current as nanoampere nA - analogic values
        self.low_p1, self.high_p1 = p_low, p_high # danzi.tn@20160728 pressure range (P in bar/10)
        self.low_q1, self.high_q1 = q_low, q_high # danzi.tn@20160728 flow-rate range (Q in lit/min/10)
        self.low_p2, self.high_p2 = p_low, p_high # danzi.tn@20160728 pressure range (P in bar/10)
        self.low_q2, self.high_q2 = q_low, q_high # danzi.tn@20160728 flow-rate range (Q in lit/min/10)

        self.p1_fit = np.polyfit([self.low1, self.high1],[self.low_p1, self.high_p1],1)
        self.p1_func = np.poly1d(self.p1_fit)
        #   Conversion from current (mA) to flow-rate (lit/min)
        self.q1_fit = np.polyfit([self.low1, self.high1],[self.low_q1, self.high_q1],1)
        self.q1_func = np.poly1d(self.q1_fit)    
        
        self.p2_fit = np.polyfit([self.low2, self.high2],[self.low_p2, self.high_p2],1)
        self.p2_func = np.poly1d(self.p2_fit)
        #   Conversion from current (mA) to flow-rate (lit/min)
        self.q2_fit = np.polyfit([self.low2, self.high2],[self.low_q2, self.high_q2],1)
        self.q2_func = np.poly1d(self.q2_fit)    
        
        self.ret_m1 = False
        self.ret_m2 = False
        self.ret_p = False
        self.afigure = a
        self.afigure2 = a2
        self.afigure3 = a3
        self.canvas = canvas
        self._bufsize = x_size
        self.databuffer_p1 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_p2 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_q1 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_q2 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_q_max = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_q_out = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.x = range(x_size)
        self.line_p1, = self.afigure3.plot(self.x, self.databuffer_p1,"b-", label='P1(An./Eng.)')
        self.line_p2, = self.afigure.plot(self.x, self.databuffer_p2,"m-", label='Pmax')
        self.line_q2, = self.afigure.plot(self.x, self.databuffer_q2,"g-",  label='Pout')
        self.line_q1, = self.afigure3.plot(self.x, self.databuffer_q1,"r-",  label='Q1(An./Eng.)')
        self.line_qmax, = self.afigure2.plot(self.x, self.databuffer_q1,"y-",  label='Qmax')
        self.line_qout, = self.afigure2.plot(self.x, self.databuffer_q1,"k-",  label='Qout')

        h1, l1 = a.get_legend_handles_labels()
        h2, l2 = a2.get_legend_handles_labels()
        h3, l3 = a3.get_legend_handles_labels()
        self.afigure.legend(h1+h2+h3, l1+l2+l3, loc=2, ncol=3, fontsize=10)
        self.pmax = 0
        self.qmax = 0
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
        self.txtMongoConnection = builder.get_object("txtMongoConnection")
        self.lstPumps = builder.get_object("lstPumps")
        self.lstMan1 = builder.get_object("lstMan1")
        self.lstMan2 = builder.get_object("lstMan2")
        self.lblDbMesg = builder.get_object("lblDbMesg")
        
        self.btnFolder = builder.get_object("btnFolder")
        self.txtOutFolder = builder.get_object("txtOutFolder")
        self.chkAnalogic =  builder.get_object("chkAnalogic")
        self.btnFolder.connect("clicked", self.on_btnFolder_clicked)
        self.time = datetime.datetime.utcnow()
        self.sMongoDbConnection = ""
        self.mongo_CLI = None
        self.mongodb = None
        self.outputFolder = None
        self.export_csv_path = None
        self.lblAnalyzed = builder.get_object("lblAnalyzed")
        self.parentWindow =  builder.get_object("windowMain")
        if smtConfig.has_option('Mongodb','Connectionstring'):
            self.txtMongoConnection.set_text(smtConfig.get('Mongodb', 'Connectionstring'))

    def on_btnFolder_clicked(self, widget):
        dialog = Gtk.FileChooserDialog("Please choose an output folder", self.parentWindow,
                                       buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,"Select", Gtk.ResponseType.OK))
        dialog.set_action(Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.set_default_size(600, 400)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            print("Select clicked")
            print("Folder selected: " + dialog.get_filename())
            self.outputFolder =  dialog.get_filename()
            self.export_csv_path = os.path.join(self.outputFolder,"test_{0}.csv".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")))
            self.txtOutFolder.set_text( dialog.get_filename())
            if not smtConfig.has_section('Output'):
                smtConfig.add_section('Output')
            smtConfig.set('Output', 'Folder', self.outputFolder)        
            with open(sCFGName, 'wb') as configfile:
                smtConfig.write(configfile)
        elif response == Gtk.ResponseType.CANCEL:
            print("Cancel clicked")

        dialog.destroy()
        
        
    def on_txtMongoConnection_changed(self,txtEdit):
       pass

    def on_btnDatabase_clicked(self,btn):
        self.sMongoDbConnection = self.txtMongoConnection.get_text()
       
        splitted = self.sMongoDbConnection.split("@")
        mongo_database = splitted[0]        
        splitted = splitted[1].split(":")
        mongo_host = splitted[0]
        mongo_port = splitted[1]
        self.mongo_CLI = MongoClient(mongo_host, int(mongo_port))
        self.mongodb = self.mongo_CLI[mongo_database]
        self.lstPumps.clear()
        self.lstMan2.clear()
        self.lstMan1.clear()
        projs =[]
        self.lblDbMesg.set_label("")
        try:
            projs = list(self.mongodb.projects.find({}))
        except pyErrors.ServerSelectionTimeoutError as timeouterr:
            self.lblDbMesg.set_label(str(timeouterr))
            logApp.debug("Database error = {0}".format(str(timeouterr)))
        if len(projs) > 0:
            if not smtConfig.has_section('Mongodb'):
                smtConfig.add_section('Mongodb')
            smtConfig.set('Mongodb', 'Connectionstring', self.sMongoDbConnection)        
            with open(sCFGName, 'wb') as configfile:
                smtConfig.write(configfile)
            gePumps = self.mongodb.groutingequipments.find({"type":"P"})
            geManifolds = self.mongodb.groutingequipments.find({"type":"M"})
            for p in gePumps:
                self.lstPumps.append([p["ipAddress"], int(p["TCPPort"]),"{0}.{1}({2}:{3})".format(p["type"],p["code"],p["ipAddress"],p["TCPPort"])])
            for p in geManifolds:
                self.lstMan2.append([p["ipAddress"], int(p["TCPPort"]),"{0}.{1}({2}:{3})".format(p["type"],p["code"],p["ipAddress"],p["TCPPort"])])
                self.lstMan1.append([p["ipAddress"], int(p["TCPPort"]),"{0}.{1}({2}:{3})".format(p["type"],p["code"],p["ipAddress"],p["TCPPort"])])
            btn.set_label("DB Connected")
            logApp.debug("Database Connected")
        else:
            btn.set_label("DB Connect")
            self.lblDbMesg.set_label("Database {0} is empty".format(mongo_database))
            logApp.debug("Database {0} is empty".format(mongo_database))
            

    def on_cmbPumps_changed(self,cmb):
        tree_iter = cmb.get_active_iter()
        if tree_iter != None:
            model = cmb.get_model()
            ip = model[tree_iter][0]
            port = model[tree_iter][1]
            builder.get_object("txtIPPump").set_text(ip)
            builder.get_object("txtPortPump").set_text(str(port))
        
    def on_cmbMan1_changed(self,cmb):
        tree_iter = cmb.get_active_iter()
        if tree_iter != None:
            model = cmb.get_model()
            ip = model[tree_iter][0]
            port = model[tree_iter][1]
            builder.get_object("txtIP1").set_text(ip)
            builder.get_object("txtPort1").set_text(str(port))
        
        
    def on_cmbMan2_changed(self,cmb):
        tree_iter = cmb.get_active_iter()
        if tree_iter != None:
            model = cmb.get_model()
            ip = model[tree_iter][0]
            port = model[tree_iter][1]
            builder.get_object("txtIP2").set_text(ip)
            builder.get_object("txtPort2").set_text(str(port))
            
            
    def logging_data(self, a):
        self.loop_no += 1        
        builder.get_object("levelbar1").set_value(len(self.listP1)%60+1)
        # print "1.1 {0}".format(t1)
        txtPout = a[11]
        txtQout = a[12]
        aIN1 = a[2]
        aIN2 = a[3]
        aIN1ENG = a[4]
        aIN2ENG = a[5]
        pDeltaPump = a[8]
        qDeltaPump = a[9]
        # print "1.2 {0}".format(t1)
        # QUI CAPITA Unhandled error in Deferred quando si perde la connessione- provare un try except e saltare il campione
        try:
            okC1 = self.client_1.connect()
            if okC1:
                rr1 = self.client_1.read_holding_registers(0,48)
            else:
                logApp.error("logging_data connection to manifold 1 failed")
                aIN1.set_text("CONNECTION ERROR")
                aIN2.set_text("CONNECTION ERROR")
                aIN1ENG.set_text("CONNECTION ERROR")
                aIN2ENG.set_text("CONNECTION ERROR")
                return False
        except:
                logApp.error("Unhandled error in Deferred - logging_data connection to manifold 1 failed")
                print "1.3 {0}".format(t1)
                aIN1.set_text("Unhandled ERROR")
                aIN2.set_text("Unhandled ERROR")
                aIN1ENG.set_text("Unhandled ERROR")
                aIN2ENG.set_text("Unhandled ERROR")
                return False
        
        # logApp.debug("logging_data 3 read_holding_registers 2 ok")
        # print "3 {0}".format(t1)
        self.client_1.close()
        if rr1.registers[test_reg_no] == test_value_1 or rr1.registers[test_reg_no] == test_value_2:
            # Manifold 1
            p_mA1 = rr1.registers[4-1]
            q_mA1 = rr1.registers[6-1]
            q_Sign = 0
            if  rr1.registers[test_reg_no] == test_value_2:
                q_Sign = rr1.registers[12-1]
            # save value into databuffer            
            for iprog in range(12):
                logApp.info("Manifold registers[{0}] = {1}".format(iprog+1, rr1.registers[iprog]))
            t1=datetime.datetime.utcnow()
            # logApp.debug("logging_data 1")
            dt_seconds = (t1-self.time).seconds

            
            # convert ANALOGIC to Digital
            p_Eng1 = self.p1_func(p_mA1)
            q_Eng1 = self.q1_func(q_mA1)
            if q_Sign:
                q_Eng1 = -1.*q_Eng1
            pEng1Display = p_Eng1/10.
            qEng1Display = q_Eng1/10.
            self.thisTick = datetime.datetime.utcnow()            
            dV = 0.0
            if self.lastTick:
                dT = self.thisTick - self.lastTick
                self.elapsed = dT.total_seconds()
                dV = qEng1Display / 60 * self.elapsed
                self.volume += dV
                #print "total_seconds = " , dT.total_seconds()
                #print "qEng1Display = " , qEng1Display
                #print "dV = " , dV
                #print "volume = ", self.volume
                builder.get_object("txtVolume").set_text("{0:.2f} lit".format(self.volume))

            self.lastTick = self.thisTick            
            
            
            
            # display del valore analogico se chkAnalogic è selezionato
            if self.chkAnalogic.get_active():
                self.databuffer_p1.append( p_mA1 )
                self.afigure3.set_ylim(a_low, a_high)
                self.afigure3.set_ylabel('Voltage (mV)')
            else:
                self.databuffer_p1.append( pEng1Display )
                self.afigure3.set_ylim(-10, 80)
                self.afigure3.set_ylabel('Eng Values')
            self.line_p1.set_ydata(self.databuffer_p1)  
            
            # display del valore analogico se chkAnalogic è selezionato
            if self.chkAnalogic.get_active():
                self.databuffer_q1.append( q_mA1 )
            else:
                self.databuffer_q1.append( qEng1Display )
            self.line_q1.set_ydata(self.databuffer_q1)
            
            self.listP1.append(p_Eng1/10.)
            aIN1.set_text(str(p_mA1))
            aIN2.set_text(str(q_mA1))
            aIN1ENG.set_text("{0} bar".format(pEng1Display ))
            aIN2ENG.set_text("{0} lit/min".format(qEng1Display))
            # INIETTORE
            #print "4 {0}".format(t1)
            if self.client_p:
                rr_p = self.client_p.read_holding_registers(500,100,unit=1)
                # print "5 {0}".format(t1)
                txtPout.set_text("{0} bar".format(rr_p.registers[16]))
                txtQout.set_text("{0} s/min {1:.2f} l/min".format(rr_p.registers[20], litCiclo*rr_p.registers[20] ))
                self.pmax = rr_p.registers[60]
                self.qmax = rr_p.registers[62]            
                self.adjustPMax.set_value(float(self.pmax) )
                self.adjustQMax.set_value(float(self.qmax))
                builder.get_object("txtPmax").set_text("{0} bar".format(rr_p.registers[60]))
                builder.get_object("txtQmax").set_text("{0} s/min {1:.2f} l/min".format(rr_p.registers[62], litCiclo*rr_p.registers[62]))
                self.pDeltaP = self.pmax - rr_p.registers[16]
                self.qDeltaP = self.qmax - rr_p.registers[20]
                self.databuffer_q_max.append(self.qmax*litCiclo)
                self.databuffer_q_out.append(rr_p.registers[20]*litCiclo)
                self.databuffer_q2.append(rr_p.registers[16] )
                self.databuffer_p2.append( self.pmax )          
                self.line_p2.set_ydata(self.databuffer_p2)
                self.line_q2.set_ydata(self.databuffer_q2)
                self.line_qout.set_ydata(self.databuffer_q_out)
                self.line_qmax.set_ydata(self.databuffer_q_max)
                
                pDeltaPump.set_text("{0} bar".format(self.pDeltaP ))
                qDeltaPump.set_text("{0} s/min {1:.2f} l/min".format(self.qDeltaP, self.qDeltaP*litCiclo ))            
                self.p_count += 1
                rr_p.registers[50] = self.p_count
                self.client_p.write_registers(500,rr_p.registers,unit=1)
            
            self.afigure.relim()
            self.afigure.autoscale_view(False, False, True)
            self.afigure2.relim()
            self.afigure2.autoscale_view(False, False, True)
            self.afigure3.relim()
            self.afigure3.autoscale_view(False, False, True)
            self.canvas.draw()            
            if self.blogFile:
                self.oneLogged = True
                # TODO btnLog set label
                # time now - before
                builder.get_object("btnLog").set_label("{0}".format(datetime.timedelta(seconds =dt_seconds)))
                log.info("%d;%f;%d;%f;%f;%f" % (p_mA1, p_Eng1, q_mA1, q_Sign, q_Eng1,self.elapsed,self.volume))
            # print "6 {0}".format(t1)
            logApp.debug("logging_data terminated successfully")      
        else:
            logApp.error( "error on test data {0}-{1} vs {2}".format(test_value_1,test_value_2,rr1.registers[test_reg_no]))
            return False
        return True


    def onDeleteWindow(self, *args):
        Gtk.main_quit(*args)

    def testConnection1(self, button):
        lblTest1 = builder.get_object("lblTest1")
        manifold_host_1 = builder.get_object("txtIP1").get_text()
        manifold_port_1 = int(builder.get_object("txtPort1").get_text())
        self.client_1 = ModbusClient(manifold_host_1, port=manifold_port_1)
        self.ret_m1=self.client_1.connect()
        lblTest1.set_text(str(self.ret_m1))
        if not smtConfig.has_section('Manifold_1'):
            smtConfig.add_section('Manifold_1')
        if self.ret_m1:
            logApp.debug("connection to manifold #1 ({0}:{1}) succedeed".format(manifold_host_1,manifold_port_1))
            rr1_103 = self.client_1.read_holding_registers(103,10)
            self.reg104_1 = tuple(rr1_103.registers )
            builder.get_object("switchMain").set_sensitive(True)
            smtConfig.set('Manifold_1', 'host', manifold_host_1)
            smtConfig.set('Manifold_1', 'port', manifold_port_1)
            with open(sCFGName, 'wb') as configfile:
                smtConfig.write(configfile)
	else:
            logApp.debug("connection to manifold #1 ({0}:{1}) failed".format(manifold_host_1,manifold_port_1))
	self.client_1.close()


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
            builder.get_object("btnShow").set_sensitive(True)
            logApp.debug("connection to Pump ({0}:{1}) succedeed".format(pump_host,pump_port))            
            self.checkPump(self.client_p)
            smtConfig.set('Pump', 'host', pump_host)
            smtConfig.set('Pump', 'port', pump_port)
            with open(sCFGName, 'wb') as configfile:
                smtConfig.write(configfile)
	else:
            builder.get_object("btnShow").set_sensitive(False)
            logApp.debug("connection to Pump ({0}:{1}) failed".format(pump_host,pump_port))
        self.client_p.close()


    def checkPump(self,client_p):
        self.p_count += 1
        rq = client_p.write_register(550,self.p_count,unit=1)
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
        self.setPumpFlowAndPressure()


    def on_btnOpenFile_clicked(self,button):
        #os.system()
        subprocess.call(["libreoffice",self.export_csv_path])


    def setPumpFlowAndPressure(self):
        if self.ret_p:
            rr_p = self.client_p.read_holding_registers(500,100,unit=1)
            self.p_count += 1
            rr_p.registers[50] = self.p_count
            rr_p.registers[60] = int(self.pmax)
            rr_p.registers[62] = int(self.qmax)
            rr_p = self.client_p.write_registers(500,rr_p.registers,unit=1)
        

    def on_btnOff_clicked(self,button):
        print("Closing application")

	logApp.debug("HDLF GUI CLOSING")
        Gtk.main_quit()

    def storeHDLF(self):
        self.pipeLength = float(builder.get_object("txtPipeLenght").get_text())
        self.pipeDiam  =  float(builder.get_object("txtPipeDiam").get_text())
        self.pipeType  = builder.get_object("txtPipeType").get_text()
        self.mixType  = builder.get_object("txtMixType").get_text()
        self.mixDensity  =  float(builder.get_object("txtMixDensity").get_text())
        self.staticHead = float(builder.get_object("txtStaticHead").get_text())
        if not smtConfig.has_section('HeadLossFactor'):
            smtConfig.add_section('HeadLossFactor')
        smtConfig.set('HeadLossFactor', 'pipeLength', self.pipeLength)
        smtConfig.set('HeadLossFactor', 'pipeDiam', self.pipeDiam)
        smtConfig.set('HeadLossFactor', 'pipeType', self.pipeType)
        smtConfig.set('HeadLossFactor', 'mixType', self.mixType)
        smtConfig.set('HeadLossFactor', 'mixDensity', self.mixDensity)
        smtConfig.set('HeadLossFactor', 'staticHead', self.staticHead)
        with open(sCFGName, 'wb') as configfile:
            smtConfig.write(configfile)
        

    def on_btnLog_toggled(self,button):
        if button.get_active():
            self.time = datetime.datetime.utcnow()
            self.blogFile = True
            self.volume = 0
            self.elapsed = 0
            self.storeHDLF()
        else:
            self.blogFile = False
            builder.get_object("btnLog").set_label("Log Data")

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
        self.client_p.close()

    def on_btnShow_clicked(self,button):
        # show dlgRegistries
        self.lstDialog = builder.get_object("dlgRegistries")
        self.liststore = builder.get_object("liststore1")
        if not self.ret_p:
            self.ret_p = self.client_p.connect()
        if self.ret_p:
            self.liststore.clear()
            rr = self.client_p.read_holding_registers(500,100,unit=1)
            for idx in [0,2,4,6,12,13,14,15,16,20,50,52,60,62]:
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

    def on_btnOKComments_clicked(self, button):
        self.dlgComments.close()

    def on_btnComments_clicked(self, button):
        # self.parentWindow
        response = self.dlgComments.run()        
        self.dlgComments.hide()

    def on_btnVolume_clicked(self, button):
        self.volume = 0
        self.elapsed = 0
    
    def on_chkAnalogic_toggled(self,chk):
        if chk.get_active():
            logApp.info( "on_chkAnalogic_toggled toggled Active" ) #
        else:
            logApp.info( "on_chkAnalogic_toggled toggled Inactive" )

    def on_spinPMax_value_changed(self,spin):
        self.pmax = int(spin.get_value())
        self.setPumpFlowAndPressure()
        
    def on_spinQMax_value_changed(self,spin):
        self.qmax = int(spin.get_value())
        self.setPumpFlowAndPressure()

    def on_switchMain_activate(self, switch,gparam):
        
        self.lblAnalyzed.set_label("...")
        if switch.get_active():
            self.listP1 = []
            self.export_csv_path = os.path.join(self.outputFolder,"test_{0}.csv".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")))            
            file_handler = logging.handlers.RotatingFileHandler(self.export_csv_path, maxBytes=5000000,backupCount=5)
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s;%(message)s')
            file_handler.setFormatter(formatter)
            if len(log.handlers) > 0:
                log.handlers[0] = file_handler
            else:    
                log.addHandler(file_handler)
            log.info("p_mA1;p_Eng1;q_mA1;q_Sign;q_Eng1;elapsed;volume")
            self.client_1 = ModbusClient(manifold_host_1, port=manifold_port_1)
            self.client_p = None
            if self.ret_p:
                self.client_p = ModbusClient(pump_host, port=pump_port)
                #self.client_1.connect()
                self.ret_p = self.client_p.connect()
                time.sleep(1.5)
                print "start connection with Pump"
            time_delay = 1./float(self.samples_no) # 1 seconds delay
            self.loop = LoopingCall(f=self.logging_data, a=(self.client_1,None, builder.get_object("txtAIN1"),builder.get_object("txtAIN2"),builder.get_object("txtAIN1ENG"),builder.get_object("txtAIN2ENG"),None,None,builder.get_object("txtAIN1ENG2"),builder.get_object("txtAIN2ENG2"),self.client_p,builder.get_object("txtPout"),builder.get_object("txtQout")))
            print "LoopingCall  created"
            self.loop.start(time_delay, now=False) # initially delay by time
            print "loop started"
            builder.get_object("txtFilePath").set_text("")
            builder.get_object("btnOpenFile").set_sensitive(False)
            builder.get_object("btnOff").set_sensitive(False)
            # self.ani = animation.FuncAnimation(self.figure, self.update_plot, interval = 1000)
        else:
            self.loop.stop()
            time.sleep(1)
            #self.client_1.close()
            if self.ret_p:
                self.client_p.close()
                print "stop connection with Pump"
            time.sleep(1)
            builder.get_object("txtFilePath").set_text(self.export_csv_path)
            builder.get_object("btnOpenFile").set_sensitive(True)
            builder.get_object("btnOff").set_sensitive(True)



hndlr = Handler(a,a2,canvas,samples_no)
hndlr.outputFolder = output_folder
hndlr.export_csv_path = os.path.join(hndlr.outputFolder,"test_{0}.csv".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")))
builder.connect_signals(hndlr)
window = builder.get_object("windowMain")
window.show_all()
reactor.run()
# Gtk.main()
