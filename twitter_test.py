#!/usr/bin/python
# TREB wordpress listing import script
# www.stardothosting.com : Managed Hosting Services
# www.shift8web.com : Web Design and Development

#Copyright (C) 2013 Star Dot Hosting Inc

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program in the LICENSE file.  If not, see <http://www.gnu.org/licenses/>


import csv, sys, urllib, urlparse, string, time, locale, os, os.path, socket, re, requests, xmlrpclib,errno
import ConfigParser
import math
import base64
import json
from datetime import date, timedelta
from ftplib import FTP
from pygeocoder import Geocoder
from pygeolib import GeocoderError
from tempfile import mkstemp
from shutil import move
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.taxonomies import *
from wordpress_xmlrpc.methods.posts import *
from wordpress_xmlrpc.methods.users import *
from wordpress_xmlrpc.methods import *

#twitter
import tweepy
import bitly_api as bitly

# debug
import pprint 

# testing
from xmlrpclib import Transport
import wordpress_xmlrpc

class SpecialTransport(Transport):
    user_agent = 'Mozilla/5.0 (Windows NT 6.0) AppleWebKit/537.31 (KHTML, like Gecko) Chrome/26.0.1410.43 Safari/537.31'

# Read configuration file parameters
Config = ConfigParser.ConfigParser()
Config.read('/root/treb-wordpress.config')

# Check command arguments
if len(sys.argv) <= 1 :
        print "\nUsage Syntax :"
        print "\ntreb_fetch.py [option1] [option2]"
        print "Option 1 : \"avail\" \"unavail\" , processes available or unavailable listings"
        print "Option 2 : Number of days prior to gather listing data"
        sys.exit(0)

###################
# Functions START #
###################

def ConfigSectionMap(section):
    dict1 = {}
    options = Config.options(section)
    for option in options:
        try:
            dict1[option] = Config.get(section, option)
            if dict1[option] == -1:
                DebugPrint("skip: %s" % option)
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1

def ftpget( localpath, remotepath, filename ) :
    # Go to destination DIR
    os.chdir(localpath)
    try:
        ftp.cwd(remotepath)
    except:
        print "Cannot change working directory..."
    #print "Local path : " + localpath
    #print "Getting remote path : " + remotepath + " and filename : " + filename
    #ftp.set_debuglevel(2)
    ftp.sendcmd("TYPE i")
    f = open(filename,"wb")
    try:
        ftp.retrbinary("RETR " + filename,f.write)
    except:
        print "File not found.. exiting .."
        os.remove(filename)

def find_id(tag):
     p = wp.call(taxonomies.GetTerms('post_tag'))
     if len(p) == 0:
          return(False)
     for thetags in p:
         if thetags.count >= 1:
             if str(thetags) in tag:
                return(True)
     return(False)

#Searches wordpress post content for MLS number (or anything else)
def unlist_mls(tag):
     p = wp.call(taxonomies.GetTerms('post_tag'))
     if len(p) == 0:
          return(False)
     print "searching tag :" + tag
     for thetags in p:
         if thetags.count >= 1:
             if str(thetags) in tag:
                 filter = { 'tags' : tag }
                 ptag = wp.call(GetPosts(filter))
                 #print "ptag : " + ptag
                 if len(ptag) == 0:
                     return(False)
                 for posttag in ptag:
                     posttag.post_status = 'unpublish'
                     print "post id : " + posttag.id
                     wp.call(DeletePost(posttag.id))
                 return(True)
     return(False)

#Take text and replace words that match an array
def replace_words(text, word_dic):
    rc = re.compile('|'.join(map(re.escape, word_dic)))
    def translate(match):
        return word_dic[match.group(0)]
    return rc.sub(translate, text)

#Silent way of removing a file if it already exists
def silentremove(file_name):
    try:
        os.remove(file_name)
    except OSError, e: # this would be "except OSError as e:" in python 3.x
        if e.errno != errno.ENOENT: # errno.ENOENT = no such file or directory
            raise # re-raise exception if a different error occured

#Filter out agents from exclude list
def ex_agent(aid, exlist):
    exlist_in = exlist.split(',')
    for excludeagent in exlist_in:
         if str(aid) == str(excludeagent):
             return(excludeagent)
    return(False)

#Filter out agent ids from include or agent match
def is_agent(aid, inlist):
    inlist_in = inlist.split(',')
    for includeagent in inlist_in:
         if str(aid) == str(includeagent):
             return(includeagent)
    return(False)


#################
# Functions END #
#################

# Get Connection and Authentication  config data
wp_url = ConfigSectionMap("wordpress")['wp_url']
wp_username = ConfigSectionMap("wordpress")['wp_username']
wp_password = ConfigSectionMap("wordpress")['wp_password']
user = ConfigSectionMap("treb")['trebuser']
password = ConfigSectionMap("treb")['trebpass']
agent_id = ConfigSectionMap("treb")['agent_id']
min_listing = Config.getint('treb', 'minimum_listing')
int_date = int(sys.argv[2])
avail_opt = sys.argv[1]
rootdir = ConfigSectionMap("treb")['root_dir']
userperm = Config.getint('wordpress', 'user_perm')
groupperm = Config.getint('wordpress', 'group_perm')
exclude_agent = ConfigSectionMap("treb")['agent_exclude']
outfile = ConfigSectionMap("treb")['output_file']
cur_path = os.getcwd()
phonemsg = ConfigSectionMap("treb")['phone_msg']
google_map_api_key = ConfigSectionMap("googlemap")['google_map_api_key']
tw_enabled = ConfigSectionMap("twitter")['enabled']
if tw_enabled == "true":
    tw_consumer = ConfigSectionMap("twitter")['consumer']
    tw_secret = ConfigSectionMap("twitter")['secret']
    tw_token = ConfigSectionMap("twitter")['access_token']
    tw_token_secret = ConfigSectionMap("twitter")['access_token_secret']
    tw_hashtags = ConfigSectionMap("twitter")['hashtags']
    tw_bitlyuser = ConfigSectionMap("twitter")['bitly_user']
    tw_bitlykey = ConfigSectionMap("twitter")['bitly_key']
walkscore_enabled = ConfigSectionMap("walkscore")['enabled']
if walkscore_enabled == "true":
    walkscore_api_key = ConfigSectionMap("walkscore")['walkscore_api_key']
    walkscore_id = ConfigSectionMap("walkscore")['walkscore_id']

# declare variables based on arguments
past_date = date.today() - timedelta(int_date)
the_day = past_date.strftime('%d')
the_mon = past_date.strftime('%m')
the_yr = past_date.strftime('%-Y')
locale.setlocale(locale.LC_ALL, 'en_US.UTF8')
    
# check if slash was added to rootdir
if rootdir.endswith('/'):
    print "Slash detected in rootdir .."
else:
    rootdir = rootdir + "/"

# Post to twitter
if tw_enabled == "true":
    print "Posting to twitter .."
    auth = tweepy.OAuthHandler(tw_consumer, tw_secret)
    auth.set_access_token(tw_token, tw_token_secret)
    api = tweepy.API(auth)
    b = bitly.Connection(access_token=tw_bitlykey)
    tweet = 'New Listing test alsjkdfklsadkljfslakfj'
    hashtag_list = tw_hashtags.split(',')
    for hash in hashtag_list:
        tweet = str(tweet) + '#' + str(hash) + ' '
    tweet_fixed = ''.join(str(e) for e in tweet)
    tweet_url = 'https://thepropertyteam.ca' 
    tweet_fixed += ' ' + str(tweet_url)
    try: 
        api.update_status(tweet_fixed[:280])
    except Exception, e:
        print 'Twitter error : ' + str(e)
