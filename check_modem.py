#!/usr/bin/python
"""
This script gets the diagnostic connection data from a Thomson DCM476 cable
modem and outputs it for Nagios - primarily so the performance data can be
graphed.
"""

from lxml import etree
import requests
import re
import sys
import argparse

def converttable(tablecode):
    """
    Function to convert supplied HTML table code into JSON (via XML)
    """
    table = etree.XML(tablecode)
    #print (etree.tostring(table, pretty_print=True))
    rows = iter(table)
    headers = [col.text for col in next(rows)]
    data = []
    for row in rows:
        values = [col.text for col in row]
        #print dict(zip(headers, values))
        data.append(dict(zip(headers, values)))
    return data


ARGPARSER = argparse.ArgumentParser(description='Check diagnostic data on Thomson Cable Modem DCM476.')
ARGPARSER.add_argument('-H', '--host', action='store', nargs=1, help="Specify the host to query")
ARGPARSER.add_argument('-f', '--forwardpath', action='store_true', help="Return only forward path diagnostic data")
ARGPARSER.add_argument('-r', '--returnpath', action='store_true', help="Return only return path diagnostic data")
ARGPARSER.add_argument('-a', '--all', action='store_true', help="Return all path diagnostic data (default)")
ARGPARSER.add_argument('-c', '--critical', action='store_true', help="If data retrieval fails, return critical")
ARGPARSER.add_argument('-w', '--warning', action='store_true', help="If data retrieval fails, return warning")
CMDLINEARGS = ARGPARSER.parse_args()

if not CMDLINEARGS.host:
    print "-H HOST must be specified.\n"
    ARGPARSER.print_help()
    sys.exit(1)

#MODEM_URL = 'http://192.168.100.1/Diagnostics.asp'
MODEM_URL = 'http://' + CMDLINEARGS.host[0] + '/Diagnostics.asp'
#MODEM_URL = 'http://localhost/Diagnostics.asp'

if CMDLINEARGS.critical or (CMDLINEARGS.critical and CMDLINEARGS.warning):
    RETURNCODE = 2
else:
    RETURNCODE = 1

try:
    DIAGNOSTICS_REQUEST = requests.get(MODEM_URL, verify=False)
except requests.exceptions.RequestException as reqexception:
    print 'Error!', reqexception
    sys.exit(RETURNCODE)

if DIAGNOSTICS_REQUEST.status_code != 200:
    print 'Error!', MODEM_URL, 'returned HTTP:', DIAGNOSTICS_REQUEST.status_code
    sys.exit(RETURNCODE)

DIAGNOSTICS = DIAGNOSTICS_REQUEST.text

# Extract the Forward Path table
FORWARDPATH = re.sub(r"^.*?Forward Path.*?(<table.*?</table>).*$", r"\1", DIAGNOSTICS, 0, re.M|re.S)
RETURNPATH = re.sub(r"^.*?Return Path.*?(<table.*?</table>).*$", r"\1", DIAGNOSTICS, 0, re.M|re.S)

#print "===="
#print FORWARDPATH
#print "===="

# Clean up the table so we can process it as XML
FORWARDPATH = re.sub("(<table) (.*?)(>)", r"\1\3", FORWARDPATH)
FORWARDPATH = re.sub("(<td) (.*?)(>)", r"\1\3", FORWARDPATH)
FORWARDPATH = re.sub("<b>(.*?)</b>", r"\1", FORWARDPATH)

# Clean up the table so we can process it as XML
RETURNPATH = re.sub("(<table) (.*?)(>)", r"\1\3", RETURNPATH)
RETURNPATH = re.sub("(<td) (.*?)(>)", r"\1\3", RETURNPATH)
RETURNPATH = re.sub("<b>(.*?)</b>", r"\1", RETURNPATH)

#print "===="
#print FORWARDPATH
#print "===="

FORWARDJSON = converttable(FORWARDPATH)
RETURNJSON = converttable(RETURNPATH)
PERFDATA = ""
RETURNDATA = ""

if (CMDLINEARGS.forwardpath or CMDLINEARGS.all) or (not CMDLINEARGS.returnpath and not CMDLINEARGS.all):
    THISFPERFDATA = ""
    for fchannels in FORWARDJSON:
        thisfchannel = fchannels["Channel"]
        for key, value in fchannels.iteritems():
            if key != "Channel":
                if key != "Modulation":
                    # Remove the suffix unless its a %
                    numericvalue = re.sub("^(.*?) (%*).*$", r"\1\2", value)
                    THISFPERFDATA = '\'FCh ' + thisfchannel + ' ' + key + '\'=' + numericvalue
                    thisreturndata = 'FWD Channel ' + thisfchannel + ' ' + key + '=' + value + '\n'
                    #print THISFPERFDATA
                    #print thisreturndata
                    PERFDATA = PERFDATA + THISFPERFDATA + ' '
                    RETURNDATA = RETURNDATA + thisreturndata

if (CMDLINEARGS.returnpath or CMDLINEARGS.all) or (not CMDLINEARGS.forwardpath and not CMDLINEARGS.all):
    THISRPERFDATA = ""
    for rchannels in RETURNJSON:
        thisrchannel = rchannels["Channel ID"]
        for key, value in rchannels.iteritems():
            if key != "Channel ID":
                if key != "Modulation":
                    numericvalue = re.sub("^(.*?) (%*).*$", r"\1\2", value)
                    THISRPERFDATA = '\'RCh ' + thisrchannel + ' ' + key + '\'=' + numericvalue
                    thisreturndata = 'RET Channel ' + thisrchannel + ' ' + key + '=' + value + '\n'
                    #print THISRPERFDATA
                    #print thisreturndata
                    PERFDATA = PERFDATA + THISRPERFDATA + ' '
                    RETURNDATA = RETURNDATA + thisreturndata

# Output the Nagios string
print RETURNDATA + '|' + PERFDATA

exit(0)
