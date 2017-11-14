#!/usr/bin/python

import csv, sys, urllib, urlparse, string, time, locale, os, os.path, socket, re, requests, xmlrpclib,errno

api_key = '1fc8f836b3e7ed1f333752ae885c854e'
lat = '43.6589094'
lng = '-79.5059876'
address = urllib.quote('31A Walford Rd,Toronto Ontario')
url = 'http://api.walkscore.com/score?format=json&address=' + address + '&lat=' + lat + '&lng=' + lng + '&wsapikey=' + api_key
print url
response = urllib.urlopen(url)
print response




