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
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from collections import defaultdict, OrderedDict
from gi.repository import Gdk
import threading

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

sCurrentWorkingdir = os.getcwd()

sCFGName = 'hdlf.cfg'
smtConfig = ConfigParser.RawConfigParser()
cfgItems = smtConfig.read(sCFGName)


logApp = logging.getLogger()
logApp.setLevel(logging.DEBUG)

output_folder = os.path.join(sCurrentWorkingdir,"out")
logAppFile = os.path.join(sCurrentWorkingdir,"hdlf_gui.log")         
file_handler = logging.handlers.RotatingFileHandler(logAppFile, maxBytes=5000000,backupCount=5)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logApp.addHandler(file_handler)
logApp.debug("HDLF GUI STARTED")

log = logging.getLogger("csv")
log.setLevel(logging.INFO)
test_reg_no = 0 # test the expected value (Machine ID, defaukt is 0x5100)
test_value = 20992 # 0x5200 => 20992

# CAVALLETTO 1
manifold_host_1 = '127.0.0.1' # 10.243.37.xx
manifold_port_1 = "5020"  # 502

# CAVALLETTO 2
manifold_host_2 = '127.0.0.1' # 10.243.37.xx
manifold_port_2 = "5021"  # 502


stdDev = 0.1

litCiclo = 2.464






builder = Gtk.Builder()
builder.add_from_file("hdlf.glade")
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
if len(cfgItems) > 0:
    
    if smtConfig.has_option('Output', 'folder'):
        output_folder = smtConfig.get('Output', 'folder')    
    if smtConfig.has_option('Manifold_1', 'host') and smtConfig.has_option('Manifold_1', 'port'):
        manifold_host_1 = smtConfig.get('Manifold_1', 'host')
        manifold_port_1 = smtConfig.get('Manifold_1', 'port')
    if smtConfig.has_option('Manifold_2', 'host') and smtConfig.has_option('Manifold_2', 'port'):
        manifold_host_2 = smtConfig.get('Manifold_2', 'host')
        manifold_port_2 = smtConfig.get('Manifold_2', 'port')

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
    builder.get_object("txtIP2").set_text(manifold_host_2)
    builder.get_object("txtPort1").set_text(manifold_port_1)
    builder.get_object("txtPort2").set_text(manifold_port_2)
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
    def __init__(self,a,a2,canvas,loop=None, samples_no=10):     
        self.txtCommentBuffer = builder.get_object("txtCommentBuffer")
        self.dlgComments = builder.get_object("dlgComments")
        self.samples_no = samples_no
        self.loop_no = 0
        self.p1Databuffer = collections.deque(maxlen=samples_no)
        self.p2Databuffer = collections.deque(maxlen=samples_no)
        self.q1Databuffer = collections.deque(maxlen=samples_no)
        self.q2Databuffer = collections.deque(maxlen=samples_no)
        
        self.loop = loop
        self.listP1 = []
        self.reg104_1 = None
        self.reg104_2 = None
        self.low1, self.high1 = 4000, 20000 # danzi.tn@20160728 current as nanoampere nA - analogic values
        self.low2, self.high2 = 4000, 20000 # danzi.tn@20160728 current as nanoampere nA - analogic values
        self.low_p1, self.high_p1 = 0, 1000 # danzi.tn@20160728 pressure range (P in bar/10)
        self.low_q1, self.high_q1 = 0, 2000 # danzi.tn@20160728 flow-rate range (Q in lit/min/10)
        self.low_p2, self.high_p2 = 0, 1000 # danzi.tn@20160728 pressure range (P in bar/10)
        self.low_q2, self.high_q2 = 0, 2000 # danzi.tn@20160728 flow-rate range (Q in lit/min/10)

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
        self.canvas = canvas
        self._bufsize = x_size
        self.databuffer_p1 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_p2 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_q1 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.databuffer_q2 = collections.deque([0.0]*self._bufsize, self._bufsize)
        self.x = range(x_size)
        self.line_p1, = self.afigure.plot(self.x, self.databuffer_p1,"b-", label='P1')
        self.line_p2, = self.afigure.plot(self.x, self.databuffer_p2,"r-", label='P2')
        self.line_q1, = self.afigure2.plot(self.x, self.databuffer_q1,"m-",  label='Q1')
        self.line_q2, = self.afigure2.plot(self.x, self.databuffer_q2,"g-",  label='Q2')

        h1, l1 = a.get_legend_handles_labels()
        h2, l2 = a2.get_legend_handles_labels()
        self.afigure.legend(h1+h2, l1+l2, loc=2, ncol=2, fontsize=10)
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
        self.btnAnalyze = builder.get_object("btnAnalyze")
        self.txtMongoConnection = builder.get_object("txtMongoConnection")
        self.lstPumps = builder.get_object("lstPumps")
        self.lstMan1 = builder.get_object("lstMan1")
        self.lstMan2 = builder.get_object("lstMan2")
        self.lblDbMesg = builder.get_object("lblDbMesg")
        
        self.btnFolder = builder.get_object("btnFolder")
        self.txtOutFolder = builder.get_object("txtOutFolder")
        self.btnFolder.connect("clicked", self.on_btnFolder_clicked)
        #self.btnAnalyze.set_sensitive(False)
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
            self.export_csv_path = os.path.join(self.outputFolder,"hdlf_{0}.csv".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")))
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
        t1=datetime.datetime.utcnow()
        # logApp.debug("logging_data 1")
        # print "1 {0}".format(t1)
        dt_seconds = (t1-self.time).seconds
        builder.get_object("levelbar1").set_value(len(self.listP1)%60+1)
        # print "1.1 {0}".format(t1)
        txtPout = a[11]
        txtQout = a[12]
        aIN1 = a[2]
        aIN2 = a[3]
        aIN1ENG = a[4]
        aIN2ENG = a[5]
        aIN12 = a[6]
        aIN22 = a[7]
        aIN1ENG2 = a[8]
        aIN2ENG2 = a[9]
        # print "1.2 {0}".format(t1)
        # QUI CAPITA Unhandled error in Deferred quando si perde la connessione- provare un try except e saltare il campione
        try:
            okC1 = self.client_1.connect()
            if okC1:
                rr1 = self.client_1.read_holding_registers(0,48)
            else:
                logApp.error("logging_data connection to manifold 1 failed")
                aIN1.set_text("CONNECTION ERROR")
                aIN2.set_text("")
                aIN1ENG.set_text("CONNECTION ERROR")
                aIN2ENG.set_text("")
                aIN12.set_text("CONNECTION ERROR")
                aIN22.set_text("")
                aIN1ENG2.set_text("CONNECTION ERROR")
                aIN2ENG2.set_text("")
                txtPout.set_text("")
                txtQout.set_text("")
                return False
        except:
                logApp.error("Unhandled error in Deferred - logging_data connection to manifold 1 failed")
                print "1.3 {0}".format(t1)
                aIN1.set_text("Unhandled ERROR")
                aIN2.set_text("")
                aIN1ENG.set_text("Unhandled ERROR")
                aIN2ENG.set_text("")
                aIN12.set_text("Unhandled ERROR")
                aIN22.set_text("")
                aIN1ENG2.set_text("Unhandled ERROR")
                aIN2ENG2.set_text("")
                txtPout.set_text("")
                txtQout.set_text("")
                return False
        # print "2 {0}".format(t1)     
        # logApp.debug("logging_data 2 read_holding_registers 1 ok")
        # QUI CAPITA Unhandled error in Deferred quando si perde la connessione- provare un try except e saltare il campione
        try:
            okC2 = self.client_2.connect()
            if okC2:
                rr2 = self.client_2.read_holding_registers(0,48)
            else:
                logApp.debug("logging_data 2 read_holding_registers 1 ok")
                aIN2.set_text("CONNECTION ERROR")
                aIN1.set_text("")
                aIN2ENG.set_text("CONNECTION ERROR")
                aIN1ENG.set_text("")
                aIN22.set_text("CONNECTION ERROR")
                aIN12.set_text("")
                aIN2ENG2.set_text("CONNECTION ERROR")
                aIN1ENG2.set_text("")
                txtPout.set_text("")
                txtQout.set_text("")
                return False
        except:
                logApp.error("Unhandled error in Deferred - logging_data connection to manifold 2 failed")
                aIN2.set_text("Unhandled ERROR")
                aIN1.set_text("")
                aIN2ENG.set_text("Unhandled ERROR")
                aIN1ENG.set_text("")
                aIN22.set_text("Unhandled ERROR")
                aIN12.set_text("")
                aIN2ENG2.set_text("Unhandled ERROR")
                aIN1ENG2.set_text("")
                txtPout.set_text("")
                txtQout.set_text("")
                print "2.3 {0}".format(t1)
                return False          
        # logApp.debug("logging_data 3 read_holding_registers 2 ok")
        # print "3 {0}".format(t1)
        self.client_1.close()
        self.client_2.close()
        if rr1.registers[test_reg_no] == test_value and rr2.registers[test_reg_no] == test_value:
            # Manifold 1
            p_mA1 = rr1.registers[4-1]# AIN1 pressione in mA in posizione 4
            if p_mA1 < self.low1:
                p_mA1 = self.low1
            if p_mA1 > self.high1:
                p_mA1 = self.high1
            # AIN2 portata in mA in posizione 6
            q_mA1 = rr1.registers[6-1]
            if q_mA1 < self.low1:
                q_mA1 = self.low1
            if q_mA1 > self.high1:
                q_mA1 = self.high1
            # save value into databuffer
            self.p1Databuffer.append(p_mA1)
            self.q1Databuffer.append(q_mA1)            
            # Manifold 2
            p_mA2 = rr2.registers[4-1]# AIN1 pressione in mA in posizione 4
            if p_mA2 < self.low2:
                p_mA2 = self.low2
            if p_mA2 > self.high2:
                p_mA2 = self.high2
            # AIN2 portata in mA in posizione 6
            q_mA2 = rr2.registers[6-1]
            if q_mA2 < self.low2:
                q_mA2 = self.low2
            if q_mA2 > self.high2:
                q_mA2 = self.high2
            # save value into databuffer
            self.p2Databuffer.append(p_mA2)
            self.q2Databuffer.append(q_mA2)
        else:
            logApp.error( "error on test data {0} vs {1} or {0} vs {2}".format(test_value,rr1.registers[test_reg_no],rr2.registers[test_reg_no]))
            return False
        # each period
        if self.loop_no % self.samples_no == 0:
            p_mA1 = np.mean(self.p1Databuffer)
            q_mA1 = np.mean(self.q1Databuffer)
            p_mA2 = np.mean(self.p2Databuffer)
            q_mA2 = np.mean(self.q2Databuffer)
            # convert ANALOGIC to Digital
            p_Eng1 = self.p1_func(p_mA1)
            q_Eng1 = self.q1_func(q_mA1)
            pEng1Display = p_Eng1/10.
            qEng1Display = q_Eng1/10.
            if pEng1Display < self.low_p1:
                pEng1Display = self.low_p1
            if qEng1Display < self.low_q1:
                qEng1Display = self.low_q1
            # convert ANALOGIC to Digital
            p_Eng2 = self.p2_func(p_mA2)
            q_Eng2 = self.q2_func(q_mA2)
            pEng2Display = p_Eng2/10.
            qEng2Display = q_Eng2/10.
            if pEng2Display < self.low_p2:
                pEng2Display = self.low_p2
            if qEng2Display < self.low_q2:
                qEng2Display = self.low_q2
            self.databuffer_p1.append( pEng1Display )
            self.line_p1.set_ydata(self.databuffer_p1)
            self.databuffer_p2.append( pEng2Display )
            self.line_p2.set_ydata(self.databuffer_p2)

            self.databuffer_q1.append( qEng1Display )
            self.line_q1.set_ydata(self.databuffer_q1)
            self.databuffer_q2.append(qEng2Display )
            self.line_q2.set_ydata(self.databuffer_q2)

            self.afigure.relim()
            self.afigure.autoscale_view(False, False, True)
            self.afigure2.relim()
            self.afigure2.autoscale_view(False, False, True)
            self.canvas.draw()
            self.listP1.append(p_Eng1/10.)
            aIN1.set_text(str(p_mA1))
            aIN2.set_text(str(q_mA1))
            aIN1ENG.set_text("{0} bar".format(pEng1Display ))
            aIN2ENG.set_text("{0} lit/min".format(qEng1Display))
            aIN12.set_text(str(p_mA2))
            aIN22.set_text(str(q_mA2))
            aIN1ENG2.set_text("{0} bar".format(pEng2Display ))
            aIN2ENG2.set_text("{0} lit/min".format(qEng2Display ))
            # INIETTORE
            #print "4 {0}".format(t1)
            rr_p = self.client_p.read_holding_registers(500,100,unit=1)
            # print "5 {0}".format(t1)
            txtPout.set_text("{0} bar".format(rr_p.registers[16]))
            txtQout.set_text("{0} c/min {1:.2f} l/min".format(rr_p.registers[20], litCiclo*rr_p.registers[20] ))
            self.pmax = rr_p.registers[60]
            self.qmax = rr_p.registers[62]            
            self.adjustPMax.set_value(float(self.pmax) )
            self.adjustQMax.set_value(float(self.qmax))
            builder.get_object("txtPmax").set_text("{0} bar".format(rr_p.registers[60]))
            builder.get_object("txtQmax").set_text("{0} c/min {1:.2f} l/min".format(rr_p.registers[62], litCiclo*rr_p.registers[62]))
            dPPump = float(rr_p.registers[16]) - float(p_Eng1)/10.
            dPManifold = p_Eng1 - p_Eng2
            if self.blogFile:
                self.oneLogged = True
                # TODO btnLog set label
                # time now - before
                builder.get_object("btnLog").set_label("{0}".format(datetime.timedelta(seconds =dt_seconds)))
                log.info("%d;%f;%d;%f;%d;%d;%d;%d;%d;%d;%d;%d;%d;%f;%d;%f;%d;%d;%d;%d;%d;%d;%d;%d;%f;%f;%s;%s;%f;%f;%d;%d;%d;%d;%f;%f" % (p_mA1, p_Eng1, q_mA1, q_Eng1,self.reg104_1[0] ,self.reg104_1[1] ,self.reg104_1[2] , self.reg104_1[3],self.reg104_1[6] ,self.reg104_1[7] ,self.reg104_1[8] , self.reg104_1[9],p_mA2, p_Eng2, q_mA2, q_Eng2,self.reg104_2[0] ,self.reg104_2[1] ,self.reg104_2[2] , self.reg104_2[3],self.reg104_2[6] ,self.reg104_2[7] ,self.reg104_2[8] , self.reg104_2[9], self.pipeLength, self.pipeDiam,self.pipeType,self.mixType,self.mixDensity,self.staticHead,rr_p.registers[16],rr_p.registers[20],self.pmax,self.qmax, dPManifold, dPPump ))
            self.p_count += 1
            rr_p.registers[50] = self.p_count
            self.client_p.write_registers(500,rr_p.registers,unit=1)
            # print "6 {0}".format(t1)
            logApp.info("logging_data terminated successfully")
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
            if self.ret_m2 and self.ret_p:
                builder.get_object("switchMain").set_sensitive(True)
            else:
                builder.get_object("switchMain").set_sensitive(False)
            smtConfig.set('Manifold_1', 'host', manifold_host_1)
            smtConfig.set('Manifold_1', 'port', manifold_port_1)
            with open(sCFGName, 'wb') as configfile:
                smtConfig.write(configfile)
	else:
            logApp.debug("connection to manifold #1 ({0}:{1}) failed".format(manifold_host_1,manifold_port_1))
	self.client_1.close()

    def testConnection2(self, button):
        lblTest2 = builder.get_object("lblTest2")
        manifold_host_2 = builder.get_object("txtIP2").get_text()
        manifold_port_2 = int(builder.get_object("txtPort2").get_text())
        self.client_2 = ModbusClient(manifold_host_2, port=manifold_port_2)
        self.ret_m2=self.client_2.connect()
        lblTest2.set_text(str(self.ret_m2))
        if not smtConfig.has_section('Manifold_2'):
            smtConfig.add_section('Manifold_2')
        if self.ret_m2:
            logApp.debug("connection to manifold #2 ({0}:{1}) succedeed".format(manifold_host_2,manifold_port_2))
            rr2_103 = self.client_2.read_holding_registers(103,10)
            self.reg104_2 = tuple(rr2_103.registers )
            if self.ret_m1 and self.ret_p:
                builder.get_object("switchMain").set_sensitive(True)
            else:
                builder.get_object("switchMain").set_sensitive(False)
            smtConfig.set('Manifold_2', 'host', manifold_host_2)
            smtConfig.set('Manifold_2', 'port', manifold_port_2)
            with open(sCFGName, 'wb') as configfile:
                smtConfig.write(configfile)
	else:
            logApp.debug("connection to manifold #2 ({0}:{1}) failed".format(manifold_host_2,manifold_port_2))
        self.client_2.close()

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
            if self.ret_m2 and self.ret_m1:
                builder.get_object("switchMain").set_sensitive(True)
            else:
                builder.get_object("switchMain").set_sensitive(False) 
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

    def on_btnAnalyze_clicked(self,button):
        self.lblAnalyzed.set_label("start analyze")
        # self.parentWindow
        response = self.dlgComments.run()

        start = self.txtCommentBuffer.get_start_iter()
        end = self.txtCommentBuffer.get_end_iter()
        txtBuff = self.txtCommentBuffer.get_text(start,end,True)
        
        self.dlgComments.hide()
        mwindow = builder.get_object("windowMain").get_window()
        ccursor = mwindow.get_cursor()
        watch_cursor = Gdk.Cursor(Gdk.CursorType.WATCH)
        mwindow.set_cursor(watch_cursor)
        clab = button.get_label()
        self.export_csv_path = builder.get_object("txtFilePath").get_text()
        if os.path.exists( self.export_csv_path ):
            print "{0} exists".format(self.export_csv_path )
            with open(self.export_csv_path, 'rb') as csvfile:
                template_vars = {}
                csv_reader = csv.DictReader(csvfile, delimiter=';')
                csv_list = list(csv_reader)
                # p_max	q_max
                dictPQ = {}
                pipeLength = 0.0
                pipeDiam = 0.0
                pipeType = "ND"
                mixType = "ND"
                mixDensity = 0.0
                # pipeLength	pipeDiam	pipeType	mixType	mixDensity	staticHead
                for row in csv_list:
                    pipeLength = float(row["pipeLength"])
                    pipeDiam = float(row["pipeDiam"])
                    pipeType = row["pipeType"]
                    mixType = row["mixType"]
                    mixDensity = float(row["mixDensity"])
                    if row["p_max"] in dictPQ:
                        dictPQ[row["p_max"]][row["q_max"]].append( np.asarray([row["q_Eng1"],row["dPManifold"]]))
                    else:
                        ddQ = defaultdict(list)
                        ddQ[row["q_max"]].append(np.asarray([row["q_Eng1"],row["dPManifold"]]))
                        dictPQ[row["p_max"]] = ddQ
                    
                """    
                for k in dictPQ:
                    print "P " , k
                    for ki in dictPQ[k]:
                        print "\tQ", ki
                        print "\t\tLen " ,len(dictPQ[k][ki])
                        print "\t\tQavg " , dictPQ[k][ki]
                        print "\t\tPavg " ,dictPQ[k][ki]
                """
                data = [ np.asarray([row["q_Eng1"],row["dPManifold"],row["q_out"],row["dPPump"] , row["p_Eng1"],row["p_Eng2"], row["p_max"],row["q_max"]], dtype=np.float64)  for row in csv_list]
                x1 = [d[0]/10. for d in data]
                y1 = [d[1]/10. for d in data]
                x2 = [d[2]*litCiclo for d in data]
                y2 = [d[3] for d in data]
                p1 = [d[4]/10. for d in data]
                p2 = [d[5]/10. for d in data]
                dP = [d[4]/10. - d[5]/10. for d in data]
                
                x1dict = defaultdict(list)
                for idx, xdata in enumerate(x1):
                    # print xdata
                    x1dict[int(xdata)].append(idx)            
                
                y1dict={}
                for key in x1dict:
                    y1array = []     
                    x1array = []                
                    for idx in x1dict[key]:
                        y1array.append(y1[idx])
                        x1array.append(x1[idx])
                    x1mean = np.mean(x1array)
                    y1mean = np.mean(y1array)
                    stdev = np.std(y1array)
                    y1dict[key] = (x1mean,y1mean,len(x1array), stdev)
                
                y1_dict = OrderedDict(sorted(y1dict.items(), key=lambda t: t[0]))
                xx1=[]
                xq1=[]
                yy1=[]
                dictItem = {}
                d_list=[]
                for k in y1_dict:
                    xx1.append(k)
                    xq1.append(y1_dict[k][0])
                    yy1.append(y1_dict[k][1])
                    dictItem = {'Q_int':k,'Q_avg':y1_dict[k][0],'dP':y1_dict[k][1],'Count':y1_dict[k][2],'StDev':y1_dict[k][3]}
                    d_list.append(dictItem)
                           
                
                avgExportPath = os.path.join(self.outputFolder,"hdlf_AVG_{0}.csv".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")))
                with open(avgExportPath, 'wb') as csv_file:
                    w = csv.DictWriter(csv_file, dictItem.keys(), delimiter=';')
                    w.writeheader()
                    for d_items in  d_list:
                        w.writerow(d_items)                
                    
                # The solution minimizes the squared error
                fit1_1, res1_1, _, _, _ =  np.polyfit(x1, y1,1,full=True)
                fit1_2, res1_2, _, _, _ =  np.polyfit(x1, y1,2,full=True)
                fit2_1, res2_1, _, _, _ =  np.polyfit(x2, y2,1,full=True)
                fit2_2, res2_2, _, _, _ =  np.polyfit(x2, y2,2,full=True)
                
                err11=0
                if len(res1_1)>0:
                    err11 = res1_1[0]
                err12=0
                if len(res1_2)>0:
                    err12 = res1_2[0]
                
                
                err21=0
                if len(res2_1)>0:
                    err21 = res2_1[0]
                err22=0
                if len(res2_2)>0:
                    err22 = res2_2[0]
               
                    
                fitavg_1_2, resavg1_2, _, _, _ =  np.polyfit(xq1, yy1,2,full=True)
                
                erravg=0
                if len(resavg1_2)>0:
                    erravg = resavg1_2[0]
                    
                p_func_fitavg_1_2 = np.poly1d(fitavg_1_2)
                tex_avg = r'$%.7fx^{2}%+.7fx%+.7f$' % tuple(fitavg_1_2)
                # print tex_avg
                p_func_fit1_1 = np.poly1d(fit1_1)
                p_func_fit1_2 = np.poly1d(fit1_2)
                p_func_fit2_1 = np.poly1d(fit2_1)
                p_func_fit2_2 = np.poly1d(fit2_2)
                xp = np.linspace(np.min(x1), np.max(x1), 100)
                fig = plt.figure(figsize=(16, 9), dpi=100)
                plt.plot(x1, y1, 'b.', label='Samples')
                plt.plot(xq1, yy1, 'co', label='Avg')
                plt.plot(xp, p_func_fit1_1(xp), 'r--', label="Linear (e={0:.3f})".format(err11))
                plt.plot(xp, p_func_fit1_2(xp), 'g-', label="Curved (e={0:.3f})".format(err12))
    
                
                plt.plot(xp, p_func_fitavg_1_2(xp), 'c-', label="Curved Avg (e={0:.3f})".format(erravg))            
                
                plt.xlabel('Flow Rate (lit/min)')
                plt.ylabel('Pressure (bar)')
                #plt.legend()
                plt.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3, ncol=3, mode="expand", borderaxespad=0.)
                plt.grid(True)
                tex1 = r'$%.7fx^{2}%+.7fx%+.7f$' % tuple(fit1_2)
                plt.text(int(np.min(x1)),np.max(y1)*0.9, "F(x)={0}".format( tex1 ), fontsize=16, va='bottom', color="g")
                plt.text(int(np.min(x1)),np.max(y1)*0.9 - 0.5, "F_Avg(x)={0}".format( tex_avg ), fontsize=16, va='bottom', color="c")
    
                template_vars["fit1_1"] = tuple(fit1_1)
                template_vars["fit1_2"] = tuple(fit1_2)
                template_vars["res1_1"] = res1_1
                template_vars["res1_2"] = res1_2
                
                template_vars["fitavg_1_2"] = tuple(fitavg_1_2)
                template_vars["resavg1_2"] = resavg1_2
                template_vars["txtBuff"] =  "<br />".join(txtBuff.split("\n"))
    
    
                imagefname = "hflf_1_{0}.png".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"))
                imagefpath = os.path.join(self.outputFolder,imagefname)
                template_vars["hflf_1"] = imagefpath
                plt.savefig(imagefpath,format="png", bbox_inches='tight', pad_inches=0)
                plt.close(fig)
    
                xp = np.linspace(np.min(x2), np.max(x2), 100)
                fig = plt.figure(figsize=(16, 9), dpi=100)
                plt.plot(x2, y2, 'b.', label='Samples')
               
                plt.plot(xp, p_func_fit2_1(xp), 'r--', label='Linear model (e={0:.3f})'.format(err21))
                plt.plot(xp, p_func_fit2_2(xp), 'g-', label='Curved model (e={0:.3f})'.format(err22))
                plt.xlabel('Flow Rate (lit/min)')
                plt.ylabel('Pressure (bar)')
                plt.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3, ncol=3, mode="expand", borderaxespad=0.)
                plt.grid(True)
                tex1 = r'$%.7fx^{2}%+.7fx%+.7f$' % tuple(fit2_2)
                plt.text(int(np.min(x2)),np.max(y2)*0.9, tex1, fontsize=16, va='bottom', color="g")
    
    
                imagefname = "hflf_2_{0}.png".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"))
                imagefpath = os.path.join(self.outputFolder,imagefname)
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
                template_vars["pipeLength"] = pipeLength
                template_vars["pipeDiam"] = pipeDiam
                template_vars["pipeType"] = pipeType
                template_vars["mixType"] = mixType
                template_vars["mixDensity"] = mixDensity
    
    
                imagefname = "time_{0}.png".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"))
                imagefpath = os.path.join(self.outputFolder,imagefname)
                template_vars["time"] = imagefpath
                plt.savefig(imagefpath,format="png", bbox_inches='tight', pad_inches=0)
                plt.close(fig)
                template_vars["issue_date"] = datetime.datetime.utcnow().strftime("%Y.%m.%d %H:%M:%S")
    
                env = Environment(loader=FileSystemLoader(os.path.join(sCurrentWorkingdir,"templates")))
                templateFile = "hdlf_template.html"
                template = env.get_template(templateFile)
                html_out = template.render(template_vars)
    
                pdffname = "hdlf_{0}.pdf".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"))
                pdfpath = os.path.join(self.outputFolder,pdffname)
                HTML(string=html_out).write_pdf(pdfpath, stylesheets=["typography.css","grid.css"])        
                self.lblAnalyzed.set_label("analyze completed")
        else:
            print "{0} does not exist".format(self.export_csv_path )      
            self.lblAnalyzed.set_label("nothing to analyze")
        button.set_label(clab)    
        mwindow.set_cursor(ccursor)
        

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
            self.export_csv_path = os.path.join(self.outputFolder,"hdlf_{0}.csv".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")))            
            file_handler = logging.handlers.RotatingFileHandler(self.export_csv_path, maxBytes=5000000,backupCount=5)
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s;%(message)s')
            file_handler.setFormatter(formatter)
            if len(log.handlers) > 0:
                log.handlers[0] = file_handler
            else:    
                log.addHandler(file_handler)
            log.info("p_mA1;p_Eng1;q_mA1;q_Eng1;p_Low1;p_High1;p_EngLow1;p_EngHigh1;q_Low1;q_High1;q_EngLow1;q_EngHigh1;p_mA2;p_Eng2;q_mA2;q_Eng2;p_Low2;p_High2;p_EngLow2;p_EngHigh2;q_Low2;q_High2;q_EngLow2;q_EngHigh2;pipeLength;pipeDiam;pipeType;mixType;mixDensity;staticHead;p_out;q_out;p_max;q_max;dPManifold;dPPump")
            self.client_1 = ModbusClient(manifold_host_1, port=manifold_port_1)
            self.client_2 = ModbusClient(manifold_host_2, port=manifold_port_2)
            self.client_p = ModbusClient(pump_host, port=pump_port)
            #self.client_1.connect()
            #self.client_2.connect()
            self.ret_p = self.client_p.connect()
            time.sleep(1.5)
            print "start connection"
            time_delay = 1./float(self.samples_no) # 1 seconds delay
            self.loop = LoopingCall(f=self.logging_data, a=(self.client_1,self.client_2, builder.get_object("txtAIN1"),builder.get_object("txtAIN2"),builder.get_object("txtAIN1ENG"),builder.get_object("txtAIN2ENG"),builder.get_object("txtAIN12"),builder.get_object("txtAIN22"),builder.get_object("txtAIN1ENG2"),builder.get_object("txtAIN2ENG2"),self.client_p,builder.get_object("txtPout"),builder.get_object("txtQout")))
            print "LoopingCall  created"
            self.loop.start(time_delay, now=False) # initially delay by time
            print "loop started"
            builder.get_object("txtFilePath").set_text("")
            builder.get_object("btnOpenFile").set_sensitive(False)
            builder.get_object("btnOff").set_sensitive(False)
            self.btnAnalyze.set_sensitive(False)
            # self.ani = animation.FuncAnimation(self.figure, self.update_plot, interval = 1000)
        else:
            self.loop.stop()
            time.sleep(1)
            #self.client_1.close()
            #self.client_2.close()
            self.client_p.close()
            print "stop connection"
            time.sleep(1)
            builder.get_object("txtFilePath").set_text(self.export_csv_path)
            builder.get_object("btnOpenFile").set_sensitive(True)
            builder.get_object("btnOff").set_sensitive(True)
            if self.oneLogged:
                self.btnAnalyze.set_sensitive(True)


hndlr = Handler(a,a2,canvas)
hndlr.outputFolder = output_folder
hndlr.export_csv_path = os.path.join(hndlr.outputFolder,"hdlf_{0}.csv".format(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")))
builder.connect_signals(hndlr)
window = builder.get_object("windowMain")
window.show_all()
reactor.run()
# Gtk.main()
