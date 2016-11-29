#!/bin/bash
# /etc/crontab
# 10 *    * * *   andrea  cd /home/sws/Documents/GitHub/pymodbus/examples/danzi.tn/ && ./export_gis.sh
python export_shp_steps.py -c
