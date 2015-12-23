#!/usr/bin/python
"""
check_kodi_playback.py
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

This script gets the playback status from Kodi and reports the currently
playing video or audio item. It also reports current file playback
percentage as performance data to allow basic graphing to indicate usage.
"""

import json, requests, pprint, argparse, urllib, sys, re

def debugprint(debugobject, debugstring):
    """
    Print debug information if running in debug mode
    """
    if CMDLINEARGS.debug:
        print "===== " + debugstring + " ====="
        pprint.pprint(debugobject)
        print "===== " + debugstring + " ====="
        print ""

def querykodi(jsonquery):
    """"
    Query the kodi server from the given URL
    """

    try:
        jsonresponse = requests.get(jsonquery, headers=HTTPHEADERS)
    except requests.exceptions.RequestException as reqexception:
        print 'Error!', reqexception
        sys.exit(RETURNCODE)

    if jsonresponse.status_code != 200:
        print 'Error!', URLPARAMETERS, 'returned HTTP:', \
              jsonresponse.status_code
        sys.exit(RETURNCODE)

    #jsonresponse.text will look like this if something is playing
    #{"id":1,"jsonrpc":"2.0","result":[{"playerid":1,"type":"video"}]}
    #and if nothing is playing:
    #{"id":1,"jsonrpc":"2.0","result":[]}

    jsondata = json.loads(jsonresponse.text)
    debugprint(jsondata, "jsondata")
    return jsondata

# Nagios return codes
NAGIOSOK = 0
NAGIOSWARNING = 1
NAGIOSCRITICAL = 2
NAGIOSUNKNOWN = 3


# Process command line arguments
ARGPARSER = argparse.ArgumentParser(description='Check Kodi playback status.')
ARGPARSER.add_argument('-H',
                       '--host',
                       action='store',
                       nargs=1,
                       help="Specify the host to query")
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

# Set the global default return code in case something goes wrong
if CMDLINEARGS.critical or (CMDLINEARGS.critical and CMDLINEARGS.warning):
    RETURNCODE = NAGIOSCRITICAL
else:
    RETURNCODE = NAGIOSWARNING

# Specifying the host is mandatory
if not CMDLINEARGS.host:
    print "-H HOST must be specified.\n"
    ARGPARSER.print_help()
    sys.exit(RETURNCODE)

KODIURL = 'http://' + CMDLINEARGS.host[0] + '/jsonrpc?'
debugprint(KODIURL, "KODIURL")

#Required header for XBMC JSON-RPC calls, otherwise you'll get a
#415 HTTP response code - Unsupported media type
HTTPHEADERS = {'content-type': 'application/json'}

# Query to get the currently playing / paused video or audio
RAWJSONQUERY = {"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}
URLPARAMETERS = urllib.urlencode({'request': json.dumps(RAWJSONQUERY)})
debugprint(URLPARAMETERS, "URLPARAMETERS")

QUERYRESULTS = querykodi(KODIURL + URLPARAMETERS)

#result is an empty list if nothing is playing or paused.
if QUERYRESULTS['result']:
    #We need the specific "playerid" of the currently playing file in order
    #to pause it
    PLAYERID = QUERYRESULTS['result'][0]["playerid"]

    # Get the currently playing item's title
    RAWJSONQUERY = {"jsonrpc": "2.0", "method": "Player.GetItem",
                    "params": {"playerid": PLAYERID,
                               "properties" : ["file"]},
                    "id": 1}
    URLPARAMETERS = urllib.urlencode({'request': json.dumps(RAWJSONQUERY)})
    debugprint(URLPARAMETERS, "URLPARAMETERS")
    QUERYRESULTS = querykodi(KODIURL + URLPARAMETERS)

    if QUERYRESULTS['result']['item']['file']:
        PLAYBACKFILE = QUERYRESULTS['result']['item']['file']

    # Clean up the filename for the output
    PLAYBACKFILE = re.sub(r"^.*\/(.*)$", r"\1", PLAYBACKFILE, 0, re.M|re.S)

    # Get the currently playing item's playback percentage
    RAWJSONQUERY = {"jsonrpc": "2.0", "method": "Player.GetProperties",
                    "params": {"playerid": PLAYERID,
                               "properties" : ["percentage"]},
                    "id": 1}
    URLPARAMETERS = urllib.urlencode({'request': json.dumps(RAWJSONQUERY)})
    debugprint(URLPARAMETERS, "URLPARAMETERS")
    QUERYRESULTS = querykodi(KODIURL + URLPARAMETERS)

    if QUERYRESULTS["result"]["percentage"]:
        print "Now playing: " + PLAYBACKFILE + \
              "|playstatus=1 playbackpercent=" + \
              "%.2f" % QUERYRESULTS['result']['percentage'] + "%"
else:
    # Kodi isn't playing anything
    print "Kodi is not playing any media.|playstatus=0 playbackpercent=0"

exit(0)
