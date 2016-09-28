# -*- coding: utf-8 -*-
import os
import sys
import getopt
from collections import OrderedDict
from datetime import datetime
import logging
import logging.handlers
from pymongo import MongoClient
from bson.objectid import ObjectId
import pandas as pandas
from openpyxl import load_workbook
from shapely.geometry import Point, LineString, shape
from shapely.ops import transform
import osgeo.osr as osr
from functools import partial
import pyproj
"""
EPSG:4326
Geodetic coordinate system

WGS 84 -- WGS84 - World Geodetic System 1984, used in GPS

EPSG:32638

WGS 84 / UTM zone 38N 
http://spatialreference.org/ref/epsg/wgs-84-utm-zone-38n/
"""
geoproject_utm = partial(pyproj.transform,pyproj.Proj(init='EPSG:4326'), pyproj.Proj(init='EPSG:32638'))
geoproject_wgs = partial(pyproj.transform,pyproj.Proj(init='EPSG:32638'), pyproj.Proj(init='EPSG:4326'))

wgs84 = pyproj.Proj(init='EPSG:4326')
utm38N = pyproj.Proj(init='EPSG:32638')

log = logging.getLogger()
log.setLevel(logging.DEBUG)
file_handler = logging.handlers.RotatingFileHandler("{0}.log".format(os.path.basename(__file__).split(".")[0]), maxBytes=5000000,backupCount=5)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

from tgrout_constants import input_sections_xls, dict_lines, dict_descr, bh_pattern, export_boreholes_xls

def main(argv):
    '''
    funzione principale
    '''
    srs = osr.SpatialReference()
    # IGRS EPSG::3889 GeodeticCRS  Iraq - onshore and offshore..
    srs.ImportFromEPSG(3889)      
    project_code = None
    mongo_host = "localhost"
    mongo_port = 27017
    mongo_database = "tgrout-development"    
    sCurrentWorkingdir = os.getcwd()
    syntax = "pyhon " + os.path.basename(__file__) + "-m <mongo host> -p <mongo port> -d <main database> -c <project code>"
    try:
        opts = getopt.getopt(argv, "hm:p:d:c:", ["mongohost=","port=","database=","project="])[0]
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
        elif opt in ("-c", "--project"):
            project_code = arg
    mongo_CLI = MongoClient(mongo_host, mongo_port)
    mongodb = mongo_CLI[mongo_database]    
    if project_code:
        pd = mongodb.projects.find_one({"code":project_code})
        sections_xls_path = os.path.join(sCurrentWorkingdir,input_sections_xls)
        if os.path.isfile(sections_xls_path):
            c_sites = mongodb.constructionsites.find({"project":pd["_id"]})
            c_sites_codes = []
            align_sets = {}
            alignmentsets_items = []
            csiteDict = {}
            for cs in c_sites:
                log.debug( "CS %s - %s (%s)" % (pd["name"],cs["name"],cs["code"]))
                exp_bh_items = []
                exp_sc_items = [] # Code	Construction Site	From	Length	To
                exp_ln_items = [] # Code	Id	Section
                exp_al_items = [] # Name	ID	Position	ConstructionSite
                csiteDict[cs["code"]] = {"bh":exp_bh_items,"sc":exp_sc_items,"ln":exp_ln_items,"al":exp_al_items}
                mongodb.sections.delete_many({'constructionSite':cs["_id"]})
                mongodb.lines.delete_many({'constructionSite':cs["_id"]})
                mongodb.alignmentsets.delete_many({'constructionSite':cs["_id"]})
                mongodb.boreholes.delete_many({'constructionSite':cs["_id"]})
                c_sites_codes.append(cs["code"])
                for line_id in range(2):
                    alignmentset_item = {'id':line_id+1, 'name':'Alignment %s (%02d)' % (dict_descr[line_id+1],line_id+1), 'constructionSite':cs["_id"] }
                    alignmentset_item['_id'] = ObjectId()
                    alignmentset_item['insertdate'] = datetime.utcnow()
                    alignmentset_item['updatedate'] = alignmentset_item['insertdate']
                    align_sets[cs["code"]+'_'+str(alignmentset_item['id'])] = alignmentset_item['_id']
                    alignmentsets_items.append(alignmentset_item)
            sections_data = pandas.read_excel(sections_xls_path, sheetname='data')
            sections_items = []
            line_items = []
            bh_items = []
            for ix, row in sections_data.iterrows():
                if row['constructionSite::constructionsites::code'] in c_sites_codes:
                    item = {}
                    skipkeys = ['constructionSite::constructionsites::code', 'to_format', 'from_format','from_x','from_y','from_z','to_x','to_y','to_z']
                    for key in sections_data:
                        if key not in skipkeys:
                            item[key] = row[key]
                    c_sites = mongodb.constructionsites.find_one({"code":row['constructionSite::constructionsites::code']})
                    item['constructionSite'] = c_sites['_id']
                    item['insertdate'] = datetime.utcnow()
                    item['updatedate'] = item['insertdate']
                    item['location'] = { "type": "LineString", "coordinates": [ [ row["from_x"], row["from_y"], row["from_z"] ], [ row["to_x"], row["to_y"], row["to_z"] ] ] }
                    item['_id'] = ObjectId()
                    sections_items.append(item) 
                    exp_sc_item = OrderedDict()
                    exp_sc_item["Code	"] = row['code']
                    exp_sc_item["Construction Site"] = c_sites["code"]
                    exp_sc_item["From	"] = row['from']
                    exp_sc_item["Length"] = row['length']
                    exp_sc_item["from_x"] = row['from_x']
                    exp_sc_item["from_y"] = row['from_y']
                    exp_sc_item["from_z"] = row['from_z']
                    exp_sc_item["to_x"] = row['to_x']
                    exp_sc_item["to_y"] = row['to_y']
                    exp_sc_item["to_z"] = row['to_z']
                    csiteDict[c_sites["code"]]["sc"].append(exp_sc_item)
                    section_segment_d = LineString([(row['from_x'],row['from_y']),(row['to_x'],row['to_y'])])
                    
                    
                    number_of_splits = len(bh_pattern)
                    unit_length = section_segment_d.length/number_of_splits
                    section_segment_m_d = transform(geoproject_utm, section_segment_d)
                    unit_length_m = section_segment_m_d.length/number_of_splits
                    
                    section_segment_m_u = section_segment_m_d.parallel_offset(1.5,'right')
                    section_segment_u = transform(geoproject_wgs, section_segment_m_u)
                    
                    section_segment_h_d = LineString([(section_segment_m_d.coords[0][0],section_segment_m_d.coords[0][1],row['from_z']),(section_segment_m_d.coords[1][0],section_segment_m_d.coords[1][1],row['to_z'])])
                    section_segment_h_u = LineString([(section_segment_m_u.coords[0][0],section_segment_m_u.coords[0][1],row['from_z']),(section_segment_m_u.coords[1][0],section_segment_m_u.coords[1][1],row['to_z'])])
                    # print "Section {0} length in degree = {1}".format(row['code'], section_segment_d.length)
                    # print "Section {0} length in metres = {1}".format(row['code'], section_segment_m_d.length)
                    # print "Distance between segments in metres = {0}".format(section_segment_m_u.distance(section_segment_m_d))
                    fromStation = item["from"]
                    section_segments = {"wgs":{1:section_segment_d,2:section_segment_u},"utm":{1:section_segment_m_d,2:section_segment_m_u},"h":{1:section_segment_h_d,2:section_segment_h_u}}
                    for line_id in range(2):
                        line_item = {'id':line_id+1, 'code':dict_lines[line_id+1], 'alignmentSet':align_sets[c_sites['code']+'_'+str(line_id+1)], 'section':item['_id'], 'constructionSite': c_sites['_id'] }
                        line_item['insertdate'] = datetime.utcnow()
                        line_item['updatedate'] = line_item['insertdate']
                        line_item['_id'] = ObjectId()
                        line_items.append(line_item)
                        exp_ln_item = OrderedDict()
                        exp_ln_item ["Code"] = dict_lines[line_id+1]
                        exp_ln_item ["Id"] = line_id+1
                        exp_ln_item ["Section"] = row['code']                        
                        csiteDict[c_sites["code"]]["ln"].append(exp_ln_item)
                        prevBhWGS84Point = None
                        prevBhUTMPoint = None
                        firstBhUTMPoint = None
                        firstBhWGS84Point = None
                        reldistStart = 0
                        reldist = 0
                        sDist = 0.0
                        for i_bh, bh in enumerate(bh_pattern):
                            # 0.0104166667 relative 0.375/36
                            # bhWGS84Point = section_segment.interpolate(i_bh*unit_length)
                            rel_pos = i_bh*unit_length_m
                            
                            ratio = 0.375/36.
                            bhWGS84Point = section_segments["wgs"][line_id+1].interpolate(i_bh*ratio, normalized=True)
                            bhUTMPoint = section_segments["utm"][line_id+1].interpolate(i_bh*ratio, normalized=True)
                            bhHPoint = section_segments["h"][line_id+1].interpolate(i_bh*ratio, normalized=True)
                            if i_bh ==0:
                                firstBhUTMPoint = bhUTMPoint
                                firstBhWGS84Point = bhWGS84Point
                            if prevBhWGS84Point:
                                reldist = prevBhUTMPoint.distance(bhUTMPoint)
                                # print "distance from previous = {0} vs unit_length_m {1}".format(reldist,unit_length_m)
                                reldistStart = firstBhUTMPoint.distance(bhUTMPoint)
                                sDist = "{0:.02f}".format(reldistStart)
                                # print "distance from start = {0} vs rel_pos {1}".format(reldistStart,rel_pos)
                            fNAN = float('nan')
                            bhStation = round(fromStation + bh['distance'],2)
                            stationId = "%.2f" % bhStation
                            boreholeid = "%03d%s-%s-%s-%s" % (item['code'],c_sites['code'],dict_lines[line_id+1], bh["type"], bh["code"] )
                            bh_item = {'constructionSite': c_sites['_id'],"section":item['_id'],"line":line_item['_id'],"type":bh["type"],"position":bh["distance"],"position_code":bh["code"],"boreholeId":boreholeid,
                                           "stationDistance_Design":bhStation,
                                           "stationId_Design":stationId,
                                           "topElevation_Design":float("{0:.02f}".format(bhHPoint.z)),
                                           "offset_Design":0,
                                           "offsetType_Design":"NA",
                                           "inclination_Design":0,
                                           "azimuth_Design":0,
                                           "diameter_Design":0,
                                           "drillBitType_Design":"NA",
                                           "drillingMethod_Design":"NA",
                                           "holeLength_Design":0,
                                           "waterDistance_Design":0,
                                           "casing_Design":"NA",
                                           "stationDistance_Build":bhStation,
                                           "stationId_Build":stationId,
                                           "topElevation_Build":float("{0:.02f}".format(bhHPoint.z)),
                                           "offset_Build":0,
                                           "offsetType_Build":"NA",
                                           "inclination_Build":0,
                                           "azimuth_Build":0,
                                           "diameter_Build":0,
                                           "drillBitType_Build":"NA",
                                           "drillingMethod_Build":"NA",
                                           "holeLength_Build":0,
                                           "waterDistance_Build":0,
                                           "casing_Build":"NA",
                                           "realPosition":float(sDist)
                                           }
                            # TODO NAN Gestire                      
                            bh_item['location'] =  { "type": "Point", "coordinates":  [ bhWGS84Point.x, bhWGS84Point.y, float("{0:.02f}".format(bhHPoint.z)) ] }
                            log.debug( "BH %s %s" % (boreholeid, stationId ))
                            bh_items.append(bh_item)
                            exp_bh_item = OrderedDict()
                            # exp_bh_item['constructionSite::constructionsites::code'] = row['constructionSite::constructionsites::code']
                            exp_bh_item['Section'] = item['code']
                            exp_bh_item['Line'] = line_item['id']
                            exp_bh_item['Type'] = bh["type"]
                            exp_bh_item['Position'] = bh["distance"]
                            # exp_bh_item['position_code'] = bh["code"]
                            # exp_bh_item['boreholeId'] = boreholeid
                            exp_bh_item['Station ID_D'] = bhStation
                            # exp_bh_item['stationId_Design'] = stationId
                            exp_bh_item['Top_Elevation_d'] = float("{0:.02f}".format(bhHPoint.z))
                            exp_bh_item['Offset_d'] = fNAN
                            exp_bh_item['Offset_type_d'] = "NA"
                            exp_bh_item['inclination_d'] = fNAN
                            exp_bh_item['azimuth_d'] = fNAN
                            exp_bh_item['diameter_d'] = fNAN
                            exp_bh_item['drillBitType_d'] = 'NA'
                            exp_bh_item['drillingMethod_d'] = 'NA'
                            exp_bh_item['holeLength_d'] = fNAN
                            exp_bh_item['waterDistance_d'] = fNAN
                            exp_bh_item['casing_d'] = 'NA'
                            exp_bh_item['Station ID_b'] = bhStation
                            # exp_bh_item['stationId_Design'] = stationId
                            exp_bh_item['Top_Elevation_b'] = float("{0:.02f}".format(bhHPoint.z))
                            exp_bh_item['Offset_b'] = fNAN
                            exp_bh_item['Offset_type_b'] = "NA"
                            exp_bh_item['inclination_b'] = fNAN
                            exp_bh_item['azimuth_b'] = fNAN
                            exp_bh_item['diameter_b'] = fNAN
                            exp_bh_item['drillBitType_b'] = 'NA'
                            exp_bh_item['drillingMethod_b'] = 'NA'
                            exp_bh_item['holeLengthb_d'] = fNAN
                            exp_bh_item['waterDistance_b'] = fNAN
                            exp_bh_item['casing_b'] = 'NA'
                            exp_bh_item['Start Drill Date'] = 'NA'
                            exp_bh_item['Stop Drill Date'] = 'NA'
                            exp_bh_item['wash Date'] = 'NA'
                            exp_bh_item['gis_x'] = bhWGS84Point.x
                            exp_bh_item['gis_y'] = bhWGS84Point.y
                            exp_bh_item['gis_z'] = float("{0:.02f}".format(bhHPoint.z))
                            exp_bh_item['realPosition']=float(sDist)
                            prevBhWGS84Point = bhWGS84Point
                            prevBhUTMPoint = bhUTMPoint
                            csiteDict[c_sites["code"]]["bh"].append(exp_bh_item)
                else:
                    print "ops, wrong for section with iteration %s" % ix
                    log.debug("Something wrong for section with iteration %s" % ix)
            mongodb.alignmentsets.insert_many(alignmentsets_items)
            mongodb.sections.insert_many(sections_items)
            mongodb.lines.insert_many(line_items)
            mongodb.boreholes.insert_many(bh_items)
            for csitecode in csiteDict:
                bh_df = pandas.DataFrame(csiteDict[csitecode]["bh"])
                sc_df = pandas.DataFrame(csiteDict[csitecode]["sc"])
                ln_df = pandas.DataFrame(csiteDict[csitecode]["ln"])
                # al_df = pandas.DataFrame(csiteDict[csitecode]["al"])
                export_boreholes_xls_path = os.path.join(sCurrentWorkingdir,export_boreholes_xls % csitecode)
                if os.path.isfile(export_boreholes_xls_path):
                    book = load_workbook(export_boreholes_xls_path)
                    writer = pandas.ExcelWriter(export_boreholes_xls_path, engine='openpyxl') 
                    writer.book = book
                    writer.sheets = dict((ws.title, ws) for ws in book.worksheets)
                else:
                    writer = pandas.ExcelWriter(export_boreholes_xls_path) 
                bh_df.to_excel(writer,sheet_name="Borehole",columns =exp_bh_item.keys(), index=False)
                sc_df.to_excel(writer,sheet_name="Section",columns =exp_sc_item.keys(), index=False)
                ln_df.to_excel(writer,sheet_name="Line",columns =exp_ln_item.keys(), index=False)
                # al_df.to_excel(writer,sheet_name="Line",columns =exp_al_item.keys(), index=False)
                writer.save()        
            log.debug("Main completed successuflly")
            
                


if __name__ == "__main__":
    main(sys.argv[1:])
