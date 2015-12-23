#!/usr/bin/python
"""
check_modem.py
Created by: David Angelovich <dangelovich@maxpowerindustries.com>
Website: http://maxpowerindustries.com

Permission to use, copy, modify, and distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

This script gets the diagnostic connection data from a Thomson DCM476 cable
modem and outputs it for Nagios - primarily so the performance data can be
graphed.
"""

from lxml import etree
import requests
import re
import sys
import argparse
import pprint

def debugprint(debugobject, debugstring):
    """
    Print debug information if running in debug mode
    """
    if CMDLINEARGS.debug:
        print "===== " + debugstring + " ====="
        pprint.pprint(debugobject)
        print "===== " + debugstring + " ====="
        print ""

def converttable(tablecode):
    """
    Function to convert supplied HTML table code into JSON (via XML)
    """
    table = etree.XML(tablecode)
    rows = iter(table)
    headers = [col.text for col in next(rows)]
    data = []
    for row in rows:
        values = [col.text for col in row]
        debugprint(dict(zip(headers, values)), "RAW JSON")
        data.append(dict(zip(headers, values)))
    return data

# Nagios return codes
NAGIOSOK = 0
NAGIOSWARNING = 1
NAGIOSCRITICAL = 2
NAGIOSUNKNOWN = 3

ARGPARSER = argparse.ArgumentParser(description='Check diagnostic data on' + \
                                                ' Thomson Cable Modem DCM476.')
ARGPARSER.add_argument('-H',
                       '--host',
                       action='store',
                       nargs=1,
                       help="Specify the host to query")
ARGPARSER.add_argument('-f',
                       '--forwardpath',
                       action='store_true',
                       help="Return only forward path diagnostic data")
ARGPARSER.add_argument('-r',
                       '--returnpath',
                       action='store_true',
                       help="Return only return path diagnostic data")
ARGPARSER.add_argument('-a',
                       '--all',
                       action='store_true',
                       help="Return all path diagnostic data (default)")
ARGPARSER.add_argument('-c',
                       '--critical',
                       action='store_true',
                       help="If data retrieval fails, return critical")
ARGPARSER.add_argument('-w',
                       '--warning',
                       action='store_true',
                       help="If data retrieval fails, return warning")
ARGPARSER.add_argument('-d',
                       '--debug',
                       action='store_true',
                       help="Enable debug mode")
CMDLINEARGS = ARGPARSER.parse_args()

if not CMDLINEARGS.host:
    print "-H HOST must be specified.\n"
    ARGPARSER.print_help()
    sys.exit(1)

MODEM_URL = 'http://' + CMDLINEARGS.host[0] + '/Diagnostics.asp'

if CMDLINEARGS.critical or (CMDLINEARGS.critical and CMDLINEARGS.warning):
    RETURNCODE = NAGIOSCRITICAL
else:
    RETURNCODE = NAGIOSWARNING

try:
    DIAGNOSTICS_REQUEST = requests.get(MODEM_URL, verify=False)
except requests.exceptions.RequestException as reqexception:
    print 'Error!', reqexception
    sys.exit(RETURNCODE)

if DIAGNOSTICS_REQUEST.status_code != 200:
    print 'Error!', MODEM_URL, 'returned HTTP:', DIAGNOSTICS_REQUEST.status_code
    sys.exit(RETURNCODE)

DIAGNOSTICS = DIAGNOSTICS_REQUEST.text
debugprint(DIAGNOSTICS, "DIAGNOSTICS")

# Extract the Forward Path table
FORWARDPATH = re.sub(r"^.*?Forward Path.*?(<table.*?</table>).*$", r"\1",
                     DIAGNOSTICS, 0, re.M|re.S)
debugprint(FORWARDPATH, "FORWARDPATH")
RETURNPATH = re.sub(r"^.*?Return Path.*?(<table.*?</table>).*$", r"\1",
                    DIAGNOSTICS, 0, re.M|re.S)
debugprint(RETURNPATH, "RETURNPATH")

# Clean up the table so we can process it as XML
FORWARDPATH = re.sub("(<table) (.*?)(>)", r"\1\3", FORWARDPATH)
debugprint(FORWARDPATH, "FORWARDPATH table tag")
FORWARDPATH = re.sub("(<td) (.*?)(>)", r"\1\3", FORWARDPATH)
debugprint(FORWARDPATH, "FORWARDPATH td tag")
FORWARDPATH = re.sub("<b>(.*?)</b>", r"\1", FORWARDPATH)
debugprint(FORWARDPATH, "FORWARDPATH b tag")

# Clean up the table so we can process it as XML
RETURNPATH = re.sub("(<table) (.*?)(>)", r"\1\3", RETURNPATH)
debugprint(RETURNPATH, "RETURNPATH table tag")
RETURNPATH = re.sub("(<td) (.*?)(>)", r"\1\3", RETURNPATH)
debugprint(RETURNPATH, "RETURNPATH td tag")
RETURNPATH = re.sub("<b>(.*?)</b>", r"\1", RETURNPATH)
debugprint(RETURNPATH, "RETURNPATH b tag")

FORWARDJSON = converttable(FORWARDPATH)
RETURNJSON = converttable(RETURNPATH)
PERFDATA = ""
RETURNDATA = ""

if (CMDLINEARGS.forwardpath or CMDLINEARGS.all) or \
   (not CMDLINEARGS.returnpath and not CMDLINEARGS.all):
    THISFPERFDATA = ""
    for fchannels in FORWARDJSON:
        thisfchannel = fchannels["Channel"]
        for key, value in fchannels.iteritems():
            if key != "Channel":
                if key != "Modulation":
                    # Remove the suffix unless its a %
                    numericvalue = re.sub("^(.*?) (%*).*$", r"\1\2", value)
                    THISFPERFDATA = '\'FCh ' + thisfchannel + ' ' + key + \
                                    '\'=' + numericvalue
                    thisreturndata = 'FWD Channel ' + thisfchannel + ' ' + \
                                     key + '=' + value + '\n'
                    debugprint(THISFPERFDATA, "THISFPERFDATA")
                    debugprint(thisreturndata, "thisreturndata")
                    PERFDATA = PERFDATA + THISFPERFDATA + ' '
                    RETURNDATA = RETURNDATA + thisreturndata
        debugprint(PERFDATA, "PERFDATA")
        debugprint(RETURNDATA, "RETURNDATA")

if (CMDLINEARGS.returnpath or CMDLINEARGS.all) or \
   (not CMDLINEARGS.forwardpath and not CMDLINEARGS.all):
    THISRPERFDATA = ""
    for rchannels in RETURNJSON:
        thisrchannel = rchannels["Channel ID"]
        for key, value in rchannels.iteritems():
            if key != "Channel ID":
                if key != "Modulation":
                    numericvalue = re.sub("^(.*?) (%*).*$", r"\1\2", value)
                    THISRPERFDATA = '\'RCh ' + thisrchannel + ' ' + key + \
                                    '\'=' + numericvalue
                    thisreturndata = 'RET Channel ' + thisrchannel + ' ' + \
                                     key + '=' + value + '\n'
                    debugprint(THISRPERFDATA, "THISRPERFDATA")
                    debugprint(thisreturndata, "thisreturndata")
                    PERFDATA = PERFDATA + THISRPERFDATA + ' '
                    RETURNDATA = RETURNDATA + thisreturndata
        debugprint(PERFDATA, "PERFDATA")
        debugprint(RETURNDATA, "RETURNDATA")

# Output the Nagios string
print RETURNDATA + '|' + PERFDATA

exit(0)
