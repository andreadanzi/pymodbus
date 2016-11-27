#!/bin/bash
# /etc/crontab
# 10 *    * * *   andrea  cd /home/andrea/Documents/GitHub/pymodbus/examples/danzi.tn/ && ./sync_tgrout_folders.sh
python syncfolders.py -c
