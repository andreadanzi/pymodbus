# -*- coding: utf-8 -*-
#!/usr/bin/env python
import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId
import logging
import logging.handlers
import os
import sys
import getopt
import datetime
import collections
from scipy.stats import randint
import numpy as np
from collections import namedtuple
import osgeo.ogr as ogr
import osgeo.osr as osr
import csv
StepRow = namedtuple('StepRow',['boreholeid','station','elevation',
                                'stage_sequence','method','top_depth',
                                'top_elevation','stage_length','mixtype',
                                'refusalP','minFlowRate','maxVolume','groutMix',
                                'startStepTime','stopStepTime','elapsedTime','productionTime',
                                'groutTake', 'flowRateAvg', 'flowRateMax', 'flowRateFinal',
                                 'pGaugeAvg', 'pGaugeMax','qAtpGaugeMax', 'pGaugeFinal','pEffAvg', 'pEffMax','qAtpEffMax', 'pEffFinal','appLugeonUnit','gin','pq'
                                ])
"""
	3	2	1	k
Q	0.0001447	-0.024499	0.86506	15.4763
P	0.000021167	-0.00403	0.30249	-0.8024
"""

bh_type_codes = {"E":"Exploratory","P":"Primary","S":"Secondary","T":"Ternary","Q":"Quanternary","L":"Quinary"}

def pOut(t):
    retV=0.000021167*t**3-0.00403*t**2+0.30249*t-0.8024
    if retV < 0.0:
        retV = 0.0
    return retV

def qOut(t):
    retV = 0.0001447*t**3-0.024499*t**2+0.86506*t+15.4763
    return retV

# client = MongoClient('localhost', 27017)
log = logging.getLogger()
log.setLevel(logging.DEBUG)
file_handler = logging.handlers.RotatingFileHandler("{0}.log".format(os.path.basename(__file__).split(".")[0]), maxBytes=5000000,backupCount=5)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

delta_rand = randint(-2, 2)
# dati di partenza
# da caricare con
# >mongoimport --db import --collection timeseries --host srv3.sws-digital.com --file import_series.json
# generati con
# >mongoexport --db tgrout-development --collection timeseries --host srv3.sws-digital.com --out import_series.json --query "{'stage':ObjectId('57c6cbb9ea71da9c2513d5b2'),'step':ObjectId('57c6cbb9ea71da9c2513d5b3')}"
# 57cd5367deeb0e074430c8f7
# 57cd5367deeb0e074430c8f8
import_refusalPressure = 10.
base_stageId = "57c6cbb9ea71da9c2513d5b2"
base_stepId = "57c6cbb9ea71da9c2513d5b3"

      
def setupStageLayer(data_source, srs):
    gs_layer = data_source.CreateLayer("boreholes", srs, ogr.wkbPoint)
    # Add the GIS fields we're interested in
    field_csite = ogr.FieldDefn("stage_id", ogr.OFTString)
    field_csite.SetWidth(24)
    gs_layer.CreateField(field_csite)
    field_csite = ogr.FieldDefn("CSite", ogr.OFTString)
    field_csite.SetWidth(24)
    gs_layer.CreateField(field_csite)
    field_name = ogr.FieldDefn("BoreholeId", ogr.OFTString)
    field_name.SetWidth(24)
    gs_layer.CreateField(field_name)
    field_type = ogr.FieldDefn("Type", ogr.OFTString)
    field_type.SetWidth(24)
    gs_layer.CreateField(field_type)
    field_align = ogr.FieldDefn("Line", ogr.OFTString)
    field_align.SetWidth(24)
    gs_layer.CreateField(field_align)
    gs_layer.CreateField(ogr.FieldDefn("Section", ogr.OFTInteger))
    gs_layer.CreateField(ogr.FieldDefn("Position", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("Latitude", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("Longitude", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("Elevation", ogr.OFTInteger))
    gs_layer.CreateField(ogr.FieldDefn("Station", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("Offset", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("Incl", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("Azimuth", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("Length", ogr.OFTReal))
    
    field_name = ogr.FieldDefn("ProType", ogr.OFTString)
    field_name.SetWidth(24)
    gs_layer.CreateField(field_name)
    field_name = ogr.FieldDefn("StgType", ogr.OFTString)
    field_name.SetWidth(24)
    gs_layer.CreateField(field_name)   
    field_name = ogr.FieldDefn("StgStatus", ogr.OFTString)
    field_name.SetWidth(24)
    gs_layer.CreateField(field_name)    
    
    gs_layer.CreateField(ogr.FieldDefn("StgID", ogr.OFTInteger))    
    gs_layer.CreateField(ogr.FieldDefn("TopElev", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("BotElev", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("RPress", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("NSteps", ogr.OFTInteger))  
    gs_layer.CreateField(ogr.FieldDefn("MaxP", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("MaxQ", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("FinalP", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("FinalQ", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("TotVol", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("TotSolid", ogr.OFTReal))
    gs_layer.CreateField(ogr.FieldDefn("ALU", ogr.OFTReal))
    field_name = ogr.FieldDefn("WPres", ogr.OFTString)
    field_name.SetWidth(24)
    gs_layer.CreateField(field_name)    
    gs_layer.CreateField(ogr.FieldDefn("WValue", ogr.OFTReal))
    return gs_layer



def createStageFeature(gs_layer,cs_data, sc_data, ln_data, bh_data, gs_data, step_related_dict):
    gs_feature = ogr.Feature(gs_layer.GetLayerDefn())
    gs_feature.SetField("stage_id", "{0}".format(gs_data["_id"]))
    gs_feature.SetField("CSite", "{0}".format(cs_data["code"]))
    gs_feature.SetField("BoreholeId", "{0}".format(bh_data["boreholeId"]))
    gs_feature.SetField("Type", "{0}".format(bh_data["type"]))
    gs_feature.SetField("Line", "{0}".format(ln_data["code"]))
    gs_feature.SetField("Section",sc_data["code"])
    gs_feature.SetField("Position",bh_data["position"])
 
    gs_feature.SetField("Longitude",bh_data["location"]["coordinates"][0])
    gs_feature.SetField("Latitude",bh_data["location"]["coordinates"][1])

    gs_feature.SetField("Elevation",bh_data["topElevation_Build"])
    gs_feature.SetField("Station",float(bh_data["stationId_Build"]))
    gs_feature.SetField("Offset",bh_data["offset_Build"])
    gs_feature.SetField("Incl",bh_data["inclination_Build"])
    gs_feature.SetField("Azimuth",bh_data["azimuth_Build"])
    gs_feature.SetField("Length",bh_data["holeLength_Build"])
    
    
    # STAGE DATA
    gs_feature.SetField("ProType", "{0}".format(gs_data["procedureType"]))  
    gs_feature.SetField("StgType", "{0}".format(gs_data["stageType"]))  
    gs_feature.SetField("StgStatus", "{0}".format(gs_data["stageStatus"]))  
    gs_feature.SetField("StgID", gs_data["ID"])   
    gs_feature.SetField("NSteps", len(gs_data["steps"]))   
    # Elevation
    topLength =  gs_data["topLength"]
    bottomLength =  gs_data["bottomLength"]
    topElev = bh_data["topElevation_Build"] - topLength * np.cos(np.radians(bh_data["inclination_Build"]))
    botElev = bh_data["topElevation_Build"] - bottomLength * np.cos(np.radians(bh_data["inclination_Build"]))
    gs_feature.SetField("TopElev",topElev)   
    gs_feature.SetField("BotElev", botElev)  
    # Design data
    gs_feature.SetField("RPress", gs_data["refusalPressure"])   
    
    # TODO STEP DATA
    gs_feature.SetField("WPres", "NA")  
    gs_feature.SetField("WValue", -99)  
    
    gs_feature.SetField("MaxP",  step_related_dict['MaxP'])    
    gs_feature.SetField("MaxQ",  step_related_dict['MaxQ'])    
    gs_feature.SetField("FinalP", step_related_dict['FinalP'])    
    gs_feature.SetField("FinalQ",  step_related_dict['FinalQ'])    
    gs_feature.SetField("TotVol", step_related_dict['TotVol'])    
    gs_feature.SetField("TotSolid", -99)     
    gs_feature.SetField("ALU", step_related_dict['ALU'])    
    
    
    # location
    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint(bh_data["location"]["coordinates"][0], bh_data["location"]["coordinates"][1], bh_data["location"]["coordinates"][2])
    gs_feature.SetGeometry(point)
    return gs_feature
    
    
def setupBoreholeLayer(data_source, srs):
    bh_layer = data_source.CreateLayer("boreholes", srs, ogr.wkbPoint)
    
    field_csite = ogr.FieldDefn("bhole_id", ogr.OFTString)
    field_csite.SetWidth(24)
    bh_layer.CreateField(field_csite)
    # Add the GIS fields we're interested in
    field_csite = ogr.FieldDefn("CSite", ogr.OFTString)
    field_csite.SetWidth(24)
    bh_layer.CreateField(field_csite)
    field_name = ogr.FieldDefn("BoreholeId", ogr.OFTString)
    field_name.SetWidth(24)
    bh_layer.CreateField(field_name)
    field_type = ogr.FieldDefn("Type", ogr.OFTString)
    field_type.SetWidth(24)
    bh_layer.CreateField(field_type)
    field_align = ogr.FieldDefn("Line", ogr.OFTString)
    field_align.SetWidth(24)
    bh_layer.CreateField(field_align)
    bh_layer.CreateField(ogr.FieldDefn("Section", ogr.OFTInteger))
    bh_layer.CreateField(ogr.FieldDefn("Position", ogr.OFTReal))
    bh_layer.CreateField(ogr.FieldDefn("Latitude", ogr.OFTReal))
    bh_layer.CreateField(ogr.FieldDefn("Longitude", ogr.OFTReal))
    bh_layer.CreateField(ogr.FieldDefn("Elevation", ogr.OFTInteger))
    bh_layer.CreateField(ogr.FieldDefn("Station", ogr.OFTReal))
    bh_layer.CreateField(ogr.FieldDefn("Offset", ogr.OFTReal))
    bh_layer.CreateField(ogr.FieldDefn("Incl", ogr.OFTReal))
    bh_layer.CreateField(ogr.FieldDefn("Azimuth", ogr.OFTReal))
    bh_layer.CreateField(ogr.FieldDefn("TotVolume", ogr.OFTReal))
    bh_layer.CreateField(ogr.FieldDefn("Length", ogr.OFTReal))
    return bh_layer

def createBoreholeFeature(bh_layer,cs_data, sc_data, ln_data, bh_data):
    bh_feature = ogr.Feature(bh_layer.GetLayerDefn())
    bh_feature.SetField("bhole_id", "{0}".format(bh_data["_id"]))
    bh_feature.SetField("CSite", "{0}".format(cs_data["code"]))
    bh_feature.SetField("BoreholeId", "{0}".format(bh_data["boreholeId"]))
    bh_feature.SetField("Type", "{0}".format(bh_data["type"]))
    bh_feature.SetField("Line", "{0}".format(ln_data["code"]))
    bh_feature.SetField("Section",sc_data["code"])
    bh_feature.SetField("Position",bh_data["position"])
 
    bh_feature.SetField("Longitude",bh_data["location"]["coordinates"][0])
    bh_feature.SetField("Latitude",bh_data["location"]["coordinates"][1])

    bh_feature.SetField("Elevation",bh_data["topElevation_Build"])
    bh_feature.SetField("Station",float(bh_data["stationId_Build"]))
    bh_feature.SetField("Offset",bh_data["offset_Build"])
    bh_feature.SetField("Incl",bh_data["inclination_Build"])
    bh_feature.SetField("Azimuth",bh_data["azimuth_Build"])
    bh_feature.SetField("Length",bh_data["holeLength_Build"])
    # fill Total Volume outside
    # bh_feature.SetField("TotVolume",bh_data["TotVolume"])
    # location
    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint(bh_data["location"]["coordinates"][0], bh_data["location"]["coordinates"][1], bh_data["location"]["coordinates"][2])
    bh_feature.SetGeometry(point)
    return bh_feature
 

def setupSectionLayer(data_source, srs):
    
   
    
    sec_layer = data_source.CreateLayer("sections", srs, ogr.wkbLineString)

    field_csite = ogr.FieldDefn("section_id", ogr.OFTString)
    field_csite.SetWidth(24)
    sec_layer.CreateField(field_csite)    
    
    sec_layer.CreateField(ogr.FieldDefn("SectionId", ogr.OFTInteger))
    sec_layer.CreateField(ogr.FieldDefn("Length", ogr.OFTReal))
    field_csite = ogr.FieldDefn("CSite", ogr.OFTString)
    field_csite.SetWidth(24)
    sec_layer.CreateField(field_csite)
    sec_layer.CreateField(ogr.FieldDefn("Latitude1", ogr.OFTReal))
    sec_layer.CreateField(ogr.FieldDefn("Longitude1", ogr.OFTReal))
    sec_layer.CreateField(ogr.FieldDefn("Elevation1", ogr.OFTInteger))
    sec_layer.CreateField(ogr.FieldDefn("Latitude2", ogr.OFTReal))
    sec_layer.CreateField(ogr.FieldDefn("Longitude2", ogr.OFTReal))
    sec_layer.CreateField(ogr.FieldDefn("Elevation2", ogr.OFTInteger))
    sec_layer.CreateField(ogr.FieldDefn("TotVolume", ogr.OFTReal))
    return sec_layer


    
def createSectionFeature(sec_layer,cs_data, sc_data, ln_data):
    sec_feature = ogr.Feature(sec_layer.GetLayerDefn())
    sec_feature.SetField("section_id", "{0}".format(sc_data["_id"]))
    sec_feature.SetField("CSite", "{0}".format(cs_data["code"]))
    sec_feature.SetField("SectionId",sc_data["code"])
    sec_feature.SetField("Length",sc_data["length"])
    sec_feature.SetField("CSite", "{0}".format(cs_data["code"]))
    # TODO fill Total Volume
    sec_feature.SetField("TotVolume",6000)
    line = ogr.Geometry(ogr.wkbLineString)
    # TODO fill Long Lat 
    line.AddPoint(1116651.439379124, 637392.6969887456)
    line.AddPoint(1188804.0108498496, 652655.7409537067)
    sec_feature.SetGeometry(line)
    return sec_feature
    
    


# python export_xlsx_steps.py -m localhost -p 27017 -d tgrout-dev -b 57ab48f1f194b0873319a12a
def main(argv):
    syntax = "python " + os.path.basename(__file__) + " -m <mongo host> -p <mongo port> -d <main database> -b <borehole_id>"
    mongo_host = "localhost"
    mongo_port = 27017
    mongo_database = "tgrout-development"
    sCurrentWorkingdir = os.getcwd()
    sDate = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")    
    borehole_id = None
    try:
        opts = getopt.getopt(argv, "hm:p:d:b:", ["mongohost=","port=","database=","borehole_id="])[0]
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
        elif opt in ("-m", "--mongohost"):
            mongo_host = arg
        elif opt in ("-d", "--database"):
            mongo_database = arg
        elif opt in ("-b", "--borehole_id"):
            borehole_id = arg
    all_boreholes = []
    mClient = MongoClient(mongo_host, mongo_port)
    db = mClient[mongo_database]
    if borehole_id:
        log.info("Trying connecting to {0}:{1}, database {2}".format(mongo_host,mongo_port,mongo_database))
        main_borehole = db.boreholes.find_one({"_id":ObjectId(borehole_id)})
        all_boreholes.append(main_borehole)
    else:
        all_boreholes = db.boreholes.find()
    
    # GIS Setup      
    
    # create the spatial reference, WGS84
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)       
    
    # set up the shapefile driver
    driver = ogr.GetDriverByName("ESRI Shapefile")  
    # BOREHOLES
    shpfname=os.path.join(sCurrentWorkingdir,"gis","boreholes_data_record.shp" )
    if os.path.exists(shpfname):
        os.remove(shpfname)
    # create boreholes data source
    bh_data_source = driver.CreateDataSource(shpfname)   
    # create the boreholes layers
    bh_layer = setupBoreholeLayer(bh_data_source,srs)
    
    # GROUT STAGES
    shpfname=os.path.join(sCurrentWorkingdir,"gis","groutstages_data_record.shp" )
    if os.path.exists(shpfname):
        os.remove(shpfname)
    # create boreholes data source
    gs_data_source = driver.CreateDataSource(shpfname) 
    gs_layer = setupStageLayer(gs_data_source,srs)
    
    shpfname=os.path.join(sCurrentWorkingdir,"gis","sections_data_record.shp" )
    if os.path.exists(shpfname):
        os.remove(shpfname)
    # create section data source
    sc_data_source = driver.CreateDataSource(shpfname)    
    # create the section layers
    sec_layer = setupSectionLayer(sc_data_source,srs)
    
    
    bh_D = []
    chainage_D = os.path.join(sCurrentWorkingdir,"gis","chainage_D.csv" )
    with open(chainage_D, 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        for r in reader:
            bh_D.append(r)

    bh_U = []            
    chainage_U = os.path.join(sCurrentWorkingdir,"gis","chainage_U.csv" )
    with open(chainage_U, 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        for r in reader:
            bh_U.append(r)
    iU=0            
    iD=0
    for enum, main_borehole in enumerate(all_boreholes):
        stages = db.stages.find({"borehole":main_borehole["_id"], "rCheckDuration":{"$exists":True}}).sort('startDateTime', pymongo.ASCENDING)
        bh_constructionsite = db.constructionsites.find_one({"_id":main_borehole["constructionSite"]})        
        bh_section = db.sections.find_one({"_id":main_borehole["section"]})
        bh_section_code = bh_section["code"]
        bh_line = db.lines.find_one({"_id":main_borehole["line"]})
        bh_line_code = bh_line["code"]
        pointWrk = None
        if bh_line_code=="D":
            pointWrk = bh_D[iD%len(bh_D)]
            iD += 1
        elif bh_line_code=="U":
            pointWrk = bh_U[iU%len(bh_U)]
            iU += 1
        main_borehole["location"]={"coordinates":[float(pointWrk["X"]),float(pointWrk["Y"]),main_borehole["topElevation_Build"]]}
        log.info("constructionSite {5} => Found borehole with Id {0}! topElevation_Build = {1}, topElevation_Build={2}, holeLength_Build={3} and holeLength_Build={4}".format(main_borehole["_id"],main_borehole["topElevation_Build"],main_borehole["topElevation_Build"],main_borehole["holeLength_Build"],main_borehole["holeLength_Build"],main_borehole["constructionSite"]))        
        # boreholeId boreholeId
        # section
        # line
        # type
        # position
        # stationId_Build
        # topElevation_Build
        # offset_Build
        # inclination_Build
        # azimuth_Build
        bh_feat = createBoreholeFeature(bh_layer,bh_constructionsite, bh_section, bh_line, main_borehole)
        bh_totVolume = 0.
        export_stages = []
        stgs = list(stages)
        for stSeq, s in enumerate( stgs ):
            log.info("ID {0} stageStatus {1}".format(s["_id"],s["stageStatus"]))
            cumV = 0.
            finalP = 0.
            finalQ = 0.
            MaxP = 0.
            MaxQ = 0.  
            for ist, step in enumerate(s["steps"]):
                rCheckDuration = s["rCheckDuration"]
                log.info("\tID {0} stepStatus {1}".format(step["_id"],step["stepStatus"]))
                timeseries = db.timeseries.find({"stage":ObjectId(s["_id"]),"step":ObjectId(step["_id"])}).sort('timestampMinute', pymongo.ASCENDING)
                lastPe = collections.deque(maxlen=rCheckDuration*60)
                lastPg = collections.deque(maxlen=rCheckDuration*60)
                lastQ = collections.deque(maxlen=rCheckDuration*60)
                avgPe = 0.
                avgPg = 0.
                avgQ = 0.
                avg3Pe = [0.,0.,0.]
                avg3Pg = [0.,0.,0.]
                avg3Q = [0.,0.,0.]
                maxPe = 0.
                maxPg = 0.
                maxQ = 0.
                qAtMaxPe = 0.
                qAtMaxPg = 0.
                iMaxAvg = 3
                
                iCount = 0
                if timeseries.count():
                    startDateTime = timeseries[0]['timestampMinute']
                    for tv in list(timeseries):
                        stopDateTime = tv['timestampMinute']
                        lastSeconds = 0
                        tvo = collections.OrderedDict(sorted(tv["values"].items(), key=lambda t: int(t[0])))
                        for vk in tvo:
                            if "avgPressureEffective" in tvo[vk]:
                                lastSeconds += 1
                                iCount = iCount + 1
                                """
                                "flowRateGaugeManifold" : 17.9745810337963,
                                "pressureGaugeManifold" : 0.625024111325,
                                "pressureEffective" : 0.520853426104166,
                                "elapsedTime" : 57000,
                                "_id" : ObjectId("57d2c23177c87c26d6a06971"),
                                "injectedGroutTakeVolume" : 15.9477824093287
                                """
                                lastQ.append(tvo[vk]["flowRateGaugeManifold"])
                                lastPe.append(tvo[vk]["pressureEffective"])
                                lastPg.append(tvo[vk]["pressureGaugeManifold"])
                                avgPe = avgPe + (tvo[vk]["pressureEffective"] - avgPe)/(iCount+1)
                                avgPg = avgPg + (tvo[vk]["pressureGaugeManifold"] - avgPg)/(iCount+1)
                                avgQ = avgQ + (tvo[vk]["flowRateGaugeManifold"] - avgQ)/(iCount+1)
                                avg3Pe[(iCount-1)%iMaxAvg] = tvo[vk]["pressureEffective"] 
                                avg3Pg[(iCount-1)%iMaxAvg] = tvo[vk]["pressureGaugeManifold"] 
                                avg3Q[(iCount-1)%iMaxAvg] = tvo[vk]["flowRateGaugeManifold"] 
                                
                                if (iCount-1)%iMaxAvg == iMaxAvg-1:
                                    if np.mean(avg3Pe) > maxPe:
                                        maxPe = np.mean(avg3Pe)
                                        qAtMaxPe = np.mean(avg3Q)
                                    if np.mean(avg3Pg) > maxPg:
                                        maxPg = np.mean(avg3Pg)
                                        qAtMaxPg = np.mean(avg3Q)
                                    if np.mean(avg3Q) > maxQ:
                                        maxQ = np.mean(avg3Q)
                            else:
                                pass
                    
                    stopDateTime = stopDateTime + datetime.timedelta(seconds=lastSeconds)                    
                    elapsedTime = stopDateTime - startDateTime
                    stageLength = s['bottomLength'] - s['topLength']
                    flowRateAvg = avgQ/stageLength
                    flowRateMax = maxQ/stageLength
                    lastQ4Mean = [dt for cnf, dt in enumerate(lastQ) if (cnf+1) % 10 ==0 ]
                    lastPe4Mean = [dt for cnf, dt in enumerate(lastPe) if (cnf+1) % 10 ==0 ]
                    lastPg4Mean = [dt for cnf, dt in enumerate(lastPg) if (cnf+1) % 10 ==0 ]
                    flowRateFinal = float('nan')
                    if len(lastQ4Mean) > 0:
                        flowRateFinal = np.mean(lastQ4Mean)/stageLength
                    pGaugeAvg = avgPg
                    pGaugeMax = maxPg
                    qAtpGaugeMax = qAtMaxPg/stageLength
                    pGaugeFinal = float('nan')
                    if len(lastPg4Mean) > 0:
                        pGaugeFinal = np.mean(lastPg4Mean)
                    pEffAvg = avgPe
                    pEffMax = maxPe
                    qAtpEffMax = qAtMaxPe/stageLength
                    if pEffMax > MaxP:
                        MaxP = pEffMax
                        MaxQ = qAtpEffMax
                    pEffFinal = float('nan')
                    if len(lastPe4Mean) > 0:
                        pEffFinal = np.mean(lastPe4Mean)
                        appLugeonUnit = 10.*flowRateFinal/pEffFinal
                    gin = step['groutTake']*pEffFinal/stageLength
                    if flowRateFinal > 0:
                        pq = pEffFinal/flowRateFinal
                    effTime = datetime.timedelta(seconds=iCount)
                    maxVolume = 99
                    headLossFactor = db.headlossfactors.find_one({'_id':ObjectId(step['headLossFactor'])})
                    groutMix = db.mixtypes.find_one({'_id':headLossFactor['mixType']})
                    cumV += step['groutTake']
                    #A21  AJ21                  
                    step_row = StepRow(main_borehole['boreholeId'], #A21+i
                                        main_borehole['stationId_Build'],
                                        main_borehole['topElevation_Build'],
                                        stSeq + 1,
                                        s['procedureType'],
                                        s['topLength'],
                                        s['topLength'],
                                        s['topLength'],
                                        step['mixTypeType'],
                                        s['refusalPressure'],
                                        s['minFlowRate'],
                                        maxVolume,
                                        groutMix['code'],
                                        str(startDateTime),
                                        str(stopDateTime),
                                        str(elapsedTime),
                                        str(effTime),
                                        step['groutTake'],
                                        flowRateAvg,
                                        flowRateMax,
                                        flowRateFinal,
                                        pGaugeAvg,
                                        pGaugeMax,
                                        qAtpGaugeMax,
                                        pGaugeFinal,
                                        pEffAvg,
                                        pEffMax,
                                        qAtpEffMax,
                                        pEffFinal,
                                        appLugeonUnit,
                                        gin,
                                        pq)               
                    export_stages.append(step_row)
                    
                    finalP = pEffFinal
                    finalQ = flowRateFinal
                else:
                    print "BH {0} Stage ID {1} step {2} stepStatus {3}".format(main_borehole['boreholeId'], s["_id"],step["_id"], step["stepStatus"])
                    log.info("\t{0}....without series".format(main_borehole['boreholeId']))   
                
            bh_totVolume += cumV
            gs_feat = createStageFeature( gs_layer,bh_constructionsite, bh_section, bh_line, main_borehole, s, {"FinalP":finalP, "FinalQ":finalQ, "MaxP":MaxP,"MaxQ":MaxQ, "TotVol":cumV, "ALU":appLugeonUnit  } )
            gs_layer.CreateFeature(gs_feat)
            gs_feat.Destroy()               
        bh_feat.SetField("TotVolume",bh_totVolume)
        bh_layer.CreateFeature(bh_feat)
        # Destroy the feature to free resources
        bh_feat.Destroy()               
        #bh_data_source.Destroy()
        #sc_data_source.Destroy()
        


if __name__ == "__main__":
    main(sys.argv[1:])
