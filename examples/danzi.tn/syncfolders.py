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


    
# python export_xlsx_steps.py -m localhost -p 27017 -d tgrout-dev -b 57ab48f1f194b0873319a12a
def main(argv):
    syntax = "python " + os.path.basename(__file__) + " -m <mongo host> -p <mongo port> -d <main database> -i <project_code> -r <root_folder> -c"
    mongo_host = "localhost"
    mongo_port = 27017
    mongo_database = "tgrout-development"
    sCurrentWorkingdir = os.getcwd()
    project_code = None
    root_folder = "/"
    bUseConfig = False
    try:
        opts = getopt.getopt(argv, "hm:p:d:i:r:c", ["mongohost=","port=","database=","project_code=","root_folder=","config"])[0]
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
        else:
            errMsg = "Error: config file {0} does not exists!".format(sCFGName)
            log.error(errMsg)
            print errMsg
            sys.exit()
        
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
                    secCode = "{0:03d}".format(sec["code"])
                    secFolder = os.path.join(cFolder,"sections", secCode)
                    folders.append(secFolder)
                    bholes = mongodb.boreholes.find({"section":sec["_id"]})
                    for bh in bholes:
                        bhCode = bh["boreholeId"]
                        bhFolder = os.path.join(secFolder,"boreholes", bhCode)
                        folders.append(bhFolder)
                        stages = mongodb.stages.find({"borehole":bh["_id"]})
                        for st in stages:
                            stCode = "{0}_GS-{1}-{2}-{3}".format(bhCode, st["ID"], st["bottomLength"], st["topLength"])
                            stFolder = os.path.join(bhFolder,"stages", stCode)
                            folders.append(stFolder)

            
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
            os.makedirs(directory)
            
if __name__ == "__main__":
    main(sys.argv[1:])
