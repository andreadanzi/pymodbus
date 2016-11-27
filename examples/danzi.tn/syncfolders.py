# -*- coding: utf-8 -*-
"""
Created on Wed Nov 23 10:36:27 2016

python syncfolders.py -d tgrout-mosul20161122 -r /home/andrea/ -i P2016_015-MOSUL

@author: andrea
"""


import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId
import logging
import logging.handlers
import os
import sys
import getopt
import ConfigParser

import urllib
import threading
from Queue import Queue

log = logging.getLogger()
log.setLevel(logging.DEBUG)
file_handler = logging.handlers.RotatingFileHandler("{0}.log".format(os.path.basename(__file__).split(".")[0]), maxBytes=5000000,backupCount=5)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

sCFGName = "{0}.cfg".format(os.path.basename(__file__).split(".")[0])

"""
projects
[Project Code]
Stores project specific content.
Example: projects/P2016_015_Mosul-Dam
[Project Code]
construction_sites
Groups constr. sites folders under the same project, example: P2016_015_Mosul-Dam/construction_sites
[Project Code]
grout_mixes
Groups grout mixes folders under the same project, example: P2016_015_Mosul-Dam/grout_mixes
[Project Code]
grouting_equipments
Groups equipments folders under the same project, example: P2016_015_Mosul-Dam/grouting_equipments
construction_sites
[Constr Site Code]
Stores construction site specific content.
Example: construction_sites/G-Gallery
grout_mixes
[Grout Type Code]
grout_mixes/A
grouting_equipments
[Equip. Type Code]
grouting_equipments/Manifolds
[Constr. Site Code]
sections
Groups sections folders under the same constr. site, example: G-Gallery/sections
sections
[Section Code]
Stores section pecific content.
Example: sections/060
[Section Code]
boreholes
Groups boreholes folders under the same section, example: 060/boreholes
boreholes
[Borehole ID]
Stores borehole specific content.
Example: boreholes/065G-U-E-06.00
[Borehole ID]
stages
Groups stage folders under the same borehole, example: 065G-U-E-06.00/stages
stages
[Stage Code]
Stores stage specific content.
Example: stages/065G-U-E-06.00_GS-4_025-030
[Grout Type Code]
[Grout Mix Code]
Stores Grout Mix specific content.
Example: A/A.01
[Equip. Type Code]
[Grout. Equip. Code]
Stores Grouting Equipment specific content.
Example: Manifolds/M01

"""

class DownloadThread(threading.Thread):
    def __init__(self, queue):
        super(DownloadThread, self).__init__()
        self.queue = queue
        self.daemon = True

    def run(self):
        while True:
            item = self.queue.get()
            url = item[3]
            destfolder = item[2]
            name = "{0}_{1}.{2}".format(item[0],item[1],item[4])
            try:
                self.download_url(url,destfolder,name)
            except Exception,e:
                print "   Error: %s"%e
                log.error( "   Error: %s"%e )
            self.queue.task_done()

    def download_url(self, url,destfolder,name ):
        # change it to a different way if you require
        dest = os.path.join(destfolder,name)
        print "[%s] Downloading %s -> %s"%(self.ident, url, dest)
        log.info( "[%s] Downloading %s -> %s"%(self.ident, url, dest) )
        urllib.urlretrieve(url, dest)
    
# python syncfolders.py -d tgrout-mosul20161122 -r /home/andrea/ -i P2016_015-MOSUL
# python syncfolders.py -c
def main(argv):
    syntax = "python " + os.path.basename(__file__) + " -m <mongo host> -p <mongo port> -d <main database> -i <project_code> -r <root_folder>  -u <baseurl> -c"
    mongo_host = "localhost"
    mongo_port = 27017
    mongo_database = "tgrout-development"
    project_code = None
    root_folder = "/"
    base_url = "http://localhost:4000/"
    bUseConfig = False
    try:
        opts = getopt.getopt(argv, "hm:p:d:i:r:u:c", ["mongohost=","port=","database=","project_code=","root_folder=","url=","config"])[0]
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
        elif opt in ("-p", "--port"):
            mongo_port = int(arg)
        elif opt in ("-c", "--config"):
            bUseConfig = True
        elif opt in ("-m", "--mongohost"):
            mongo_host = arg
        elif opt in ("-u", "--url"):
            base_url = arg
        elif opt in ("-d", "--database"):
            mongo_database = arg
        elif opt in ("-r", "--root_folder"):
            root_folder = arg
        elif opt in ("-i", "--project_code"):
            project_code = arg
    

    if bUseConfig:
        if os.path.exists(sCFGName):    
            syncConfig = ConfigParser.RawConfigParser()
            cfgItems = syncConfig.read(sCFGName)
            mongo_host = syncConfig.get('MongoDB', 'host')    
            mongo_database = syncConfig.get('MongoDB', 'db')    
            mongo_port = int(syncConfig.get('MongoDB', 'port')) 
            project_code = syncConfig.get('Project', 'code')     
            root_folder = syncConfig.get('System', 'root_folder')   
            base_url = syncConfig.get('System', 'base_url')  
        else:
            errMsg = "Error: config file {0} does not exists!".format(sCFGName)
            log.error(errMsg)
            print errMsg
            sys.exit()

    if len(base_url) > 0 and base_url[-1] != '/':
        base_url = base_url + "/"
    if os.path.exists(root_folder):
        log.debug("Root folder {0} exists".format(root_folder))
    else:
        errMsg = "Error: root folder {0} does not exists!".format(root_folder)
        log.error(errMsg)
        print errMsg
        sys.exit()
           
    mClient = MongoClient(mongo_host, mongo_port)
    mongodb = mClient[mongo_database]
    folders = []
    downloads = Queue()
    root_folder = os.path.join(root_folder, "projects")
    folders.append(root_folder)
    if project_code:
        pd = mongodb.projects.find_one({"code":project_code})
        if pd:
            pCode = pd["code"]
            pFolder = os.path.join(root_folder, pCode)
            folders.append(pFolder)
            cSites = mongodb.constructionsites.find({"project":pd["_id"]})
            for cs in cSites:
                cCode = cs["code"]
                cFolder = os.path.join(pFolder,"construction_sites", cCode)
                folders.append(cFolder)
                sections = mongodb.sections.find({"constructionSite":cs["_id"]})
                for sec in sections:
                    bAppendSection = False
                    secCode = "{0:03d}".format(sec["code"])
                    secFolder = os.path.join(cFolder,"sections", secCode)
                    bholes = mongodb.boreholes.find({"section":sec["_id"]})
                    for bh in bholes:
                        bhCode = bh["boreholeId"]
                        bAppendBorehole = False
                        # http://localhost:4000/api/boreholes/export-excel/580f648d73c8240047707508 borehole_047S-D-P-06.00_export
                        borehole_url = base_url + "api/boreholes/export-excel/" + str(bh["_id"])
                        bhFolder = os.path.join(secFolder,"boreholes", bhCode)
                        stages = mongodb.stages.find({"borehole":bh["_id"]})
                        for st in stages:
                            # http://localhost:4000/api/stages/report/5838321d16a236ea43d5bef9
                            stage_url = base_url + "api/stages/report/" + str(st["_id"])
                            stCode = "{0}_GS-{1}-{2}-{3}".format(bhCode, st["ID"], st["bottomLength"], st["topLength"])
                            stFolder = os.path.join(bhFolder,"stages", stCode)
                            if st["stageStatus"] == "CLOSED":
                                bAppendBorehole = True
                                bAppendSection = True
                                downloads.put(('stage', stCode, stFolder, stage_url, "pdf"))
                            folders.append(stFolder)
                        if bAppendBorehole:
                            folders.append(bhFolder)
                            downloads.put(('borehole',bhCode, bhFolder, borehole_url, "xlsx"))                                        
                    if bAppendSection:                        
                        folders.append(secFolder)
            gMixes = mongodb.mixtypes.find({"project":pd["_id"]})
            for gm in gMixes:
                gmCode = gm["code"]
                gmType = gm["type"]
                gmFolder = os.path.join(pFolder,"grout_mixes", gmType)
                gmFolder = os.path.join(gmFolder,gmCode)
                folders.append(gmFolder)
            
            gEquips = mongodb.groutingequipments.find({"project":pd["_id"]})
            for ge in gEquips:
                geCode = ge["code"]
                geType = ge["type"]
                geFolder = os.path.join(pFolder,"equipments", geType)
                folders.append(gmFolder)
                geFolder = os.path.join(geFolder,geCode)
                folders.append(geFolder)
    else:
        errMsg = "Error: project code is mandatory!"
        log.error(errMsg)
        print errMsg
    
    for directory in folders:
        if not os.path.exists(directory):
            log.info("{0} does not exists".format(directory))
            os.makedirs(directory)
            log.info("{0} created".format(directory))
  
    ##     
    numthreads=4
    for i in range(numthreads):
        t = DownloadThread(downloads)
        t.start()  
    downloads.join() 

            
if __name__ == "__main__":
    main(sys.argv[1:])
