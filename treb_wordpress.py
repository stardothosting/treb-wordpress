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
walkscore_enabled = ConfigSectionMap("walkscore")['enabled']
if walkscore_enabled == "true":
    walkscore_api_key = ConfigSectionMap("walkscore")['walkscore_api_key']
    walkscore_id = ConfigSectionMap("walkscore")['walkscore_id']

# Get blog URL
wp_site = wordpress_xmlrpc.Client(wp_url,wp_username,wp_password,transport=SpecialTransport())
siteurl = wp_site.call(options.GetOptions(['home_url']))[0].value



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

# build the url query string
url = "http://3pv.torontomls.net/data3pv/DownLoad3PVAction.asp?user_code=" + user + "&password=" + password + "&sel_fields=*&dlDay=" + the_day + "&dlMonth=" + the_mon + "&dlYear=" + the_yr + "&order_by=&au_both=" + avail_opt + "&dl_type=file&incl_names=yes&use_table=MLS&send_done=no&submit1=Submit&query_str=lud%3E%3D%27" + the_yr + the_mon + the_day + "%27"

#print url
#sys.exit()

# retrieve URL and  write results to filename
silentremove(outfile)
urllib.urlretrieve(url,outfile)

# Available or Unavailable Listing Logic
if avail_opt == "avail":

    # read the csv file
    f = open(outfile, 'r') #open file
    try:
        r = csv.reader(f) #init csv reader
        r.next()
        for row in r:
            description = row[2]
            streetname = row[273]
            streetnumber = row[275]
            streetsuffix = row[276]
            address = row[3]
            apt_num = row[7]
            postalcode = row[330]
            bathrooms = row[10]
            bedrooms = row[15]
            bedplus = row[16]
            houseclass = row[29]
            extras = row[69]
            listagent = row[111]
            listprice = row[120]
            mlsnumber = row[130]
            squarefoot = row[269]
            virtualtour = row[292]
            pictures = row[174]
            inputdate = row[174]
            lastupdate = row[123]
            solddate = row[24]
            agentid = row[333]
            municipality = row[450]
            province = row[48]
            country = 'Canada'
            
            #Sanitize Variables
            listpricefix = locale.currency(int(listprice), grouping=True )
            addressfix = address + ', ' + municipality + ', ' + province
            #description = description.replace(":", "\:").replace("/", "\/").replace("&", "\&")
            #virtualtour = virtualtour.replace(":", "\:").replace("/", "\/").replace("&", "\&")
            print "MLS NUMBER : " + mlsnumber


            # Set category and verify if other agent listing is over minimum_listing in config file
            include = is_agent(agentid, agent_id)
            if include: 
                listingcategory = "Listings"
            else:
                if int(listprice) < min_listing:
                    print "Listing " + mlsnumber + " is below $" + str(min_listing) + " , Not adding"
                    continue
                else:
                    # Check if agent is in exclude list
                    exclude = ex_agent(agentid, exclude_agent)
                    if exclude:
                        print "Agent ID " + str(exclude) + " in exclude list, skipping .. "
                        continue
                    else:
                        print "Agent ID " + str(agentid) + " not in exclude list .. "
                        listingcategory = "OtherListings"

                    # Get the latitude + longitude variables
            print "Address for geocoder : " + addressfix
            try:
                treb_geocoder = Geocoder(api_key=google_map_api_key)
                results = treb_geocoder.geocode(addressfix)
                lat, lng = results[0].coordinates
                lat = str(lat)
                lng = str(lng)
            except GeocoderError as e:
                print('*** Caught exception: %s: %s' % (e.__class__, e))
                print 'Error getting address, skipping'
                (lat,lng) = (0.0,0.0)
                continue

                # Set variable for virtual tour
            if virtualtour == "":
                virtualtour = "N/A"
            else:
                virtualtour = "<strong>Virtual Tour:</strong> <a href=\"" + virtualtour + "\" target=\"_new\"><b>Click here for virtual tour</b></a>"

            # Start prepping the uploads folder for the MLS listing images
            if pictures == "Y":
                mlsimage = mlsnumber[-3:]
                print "MLS Image : " + mlsimage

                # Create upload folder if it doesnt exist
                if not os.path.exists(rootdir + '/wp-content/uploads/treb/' + mlsnumber):
                        os.makedirs(rootdir + '/wp-content/uploads/treb/' + mlsnumber)

                else:
                        print "No photos ..."

                # Generate post content from the template file
            template_read = open(cur_path + "/listing_template.txt", "r")
            template_text = template_read.read()
            template_read.close()

            # Prepare Base64 encoded string for gallery 
            listing_gallery_1 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s.jpg" % (siteurl, mlsnumber, mlsnumber))
            listing_gallery_2 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_2.jpg" % (siteurl, mlsnumber, mlsnumber))
            listing_gallery_3 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_3.jpg" % (siteurl, mlsnumber, mlsnumber))
            listing_gallery_4 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_4.jpg" % (siteurl, mlsnumber, mlsnumber))
            listing_gallery_5 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_5.jpg" % (siteurl, mlsnumber, mlsnumber))
            listing_gallery_6 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_6.jpg" % (siteurl, mlsnumber, mlsnumber))
            listing_gallery_7 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_7.jpg" % (siteurl, mlsnumber, mlsnumber))
            listing_gallery_8 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_8.jpg" % (siteurl, mlsnumber, mlsnumber))
            listing_gallery_9 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_9.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_10 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_10.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_11 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_11.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_12 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_12.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_13 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_13.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_14 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_14.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_15 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_15.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_16 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_16.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_17 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_17.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_18 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_18.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_19 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_19.jpg"% (siteurl, mlsnumber, mlsnumber))
            listing_gallery_20 = urllib.quote_plus("%s/wp-content/uploads/treb/%s/%s_20.jpg"% (siteurl, mlsnumber, mlsnumber))

            listing_gallery = listing_gallery_1 + "%2C" + listing_gallery_2 + "%2C" + listing_gallery_3 + "%2C" + listing_gallery_4 + "%2C" + listing_gallery_5 + "%2C" + listing_gallery_6 + "%2C" + listing_gallery_7 + "%2C" + listing_gallery_8 + "%2C" + listing_gallery_9 + "%2C" + listing_gallery_10 + "%2C" + listing_gallery_11 + "%2C" + listing_gallery_12 + "%2C" + listing_gallery_13 + "%2C" + listing_gallery_14 + "%2C" + listing_gallery_15 + "%2C" + listing_gallery_16 + "%2C" + listing_gallery_17 + "%2C" + listing_gallery_18 + "%2C" + listing_gallery_19 + "%2C" + listing_gallery_20

            listing_gallery_base64 = base64.b64encode(listing_gallery)
            if walkscore_enabled == 'true':
                walkscore_code = """
<script type='text/javascript'>
var ws_wsid = '%s';
var ws_address = '%s %s %s, %s, %s, %s'
var ws_format = 'square';
var ws_width = '300';
var ws_height = '300';
</script><style type='text/css'>#ws-walkscore-tile{position:relative;text-align:left}#ws-walkscore-tile *{float:none;}</style><div id='ws-walkscore-tile'></div><script type='text/javascript' src='https://www.walkscore.com/tile/show-walkscore-tile.php'></script>
""" % (walkscore_id, streetnumber, streetname, streetsuffix, municipality, province, country)
            else:
                walkscore_code = " "

            # Populate APT Number
            if apt_num:
                apt_num = '(apt #' + apt_num + ')'
                

            #Replacements from the template
            reps = {'%STREETNUMBER%':streetnumber, '%STREETNAME%':streetname + ' ' + streetsuffix, '%APT_NUM%':apt_num, '%POSTALCODE%':postalcode, '%LISTPRICE%':listpricefix, '%MLSNUMBER%':mlsnumber, '%BATHROOMS%':bathrooms, '%BEDROOMS%':bedrooms, '%SQFOOTAGE%':squarefoot, '%DESCRIPTION%':description, '%VIRTUALTOUR%':virtualtour, '%WPBLOG%':siteurl, '%PHONEMSG%':phonemsg, '%MAPLAT%':lat, '%MAPLNG%':lng, '%BASE64IMAGES%':listing_gallery_base64, '%GOOGLEMAPAPI%':google_map_api_key,  '%WALKSCORECODE%':walkscore_code }
            post_excerpt = """
<span class="tpt-ex-address">%s %s</span>
<span class="tpt-ex-price">%s</span>
<span class="tpt-ex-mls">MLS : %s</span>""" % (streetnumber, streetname, listpricefix, mlsnumber)

            # Prepare the post
            wp = wordpress_xmlrpc.Client(wp_url,wp_username,wp_password,transport=SpecialTransport())
            post = WordPressPost()
            post.title = addressfix
            post.content = replace_words(template_text, reps)
            post.excerpt = post_excerpt
            post.terms_names = {
                'post_tag': [mlsnumber],
                'category': [listingcategory],
            }

            # Check if post exists already
            print "Post title : " + post.title
            print "Checking if post exists .."
            #post_id = find_id(post.title)
            post_id = find_id(mlsnumber)
            if post_id:
                # check if sold date variable is set and update existing post to reflect the property as sold
                if solddate == "" :
                    print "Sorry, a post ID exists already"
                else :
                    post.title = "[SOLD!] " + post.title
                    wp.call(posts.EditPost(post.id, post))
            else:
                print "No existing duplicate post found .. posting to wordpress .."
                # GET The image files via FTP
                print "Starting FTP connection to get listing photos .."
                ftp = FTP("3pv.torontomls.net", timeout=320)
                ftp.set_debuglevel(0)
                try:
                    ftp.login(user + "@photos", password)
                except:
                    print "Error, could not login.."
                try:
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/1/" + mlsimage + '/', mlsnumber + ".jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/2/" + mlsimage + '/', mlsnumber + "_2.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/3/" + mlsimage + '/', mlsnumber + "_3.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/4/" + mlsimage + '/', mlsnumber + "_4.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/5/" + mlsimage + '/', mlsnumber + "_5.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/6/" + mlsimage + '/', mlsnumber + "_6.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/7/" + mlsimage + '/', mlsnumber + "_7.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/8/" + mlsimage + '/', mlsnumber + "_8.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/9/" + mlsimage + '/', mlsnumber + "_9.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/10/" + mlsimage + '/', mlsnumber + "_10.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/11/" + mlsimage + '/', mlsnumber + "_11.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/12/" + mlsimage + '/', mlsnumber + "_12.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/13/" + mlsimage + '/', mlsnumber + "_13.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/14/" + mlsimage + '/', mlsnumber + "_14.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/15/" + mlsimage + '/', mlsnumber + "_15.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/16/" + mlsimage + '/', mlsnumber + "_16.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/17/" + mlsimage + '/', mlsnumber + "_17.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/18/" + mlsimage + '/', mlsnumber + "_18.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/19/" + mlsimage + '/', mlsnumber + "_19.jpg")
                    ftpget( rootdir + "/wp-content/uploads/treb/" + mlsnumber, "/mlsphotos/20/" + mlsimage + '/', mlsnumber + "_20.jpg")
                except:
                    print "Error downloading images via FTP ..."
                try:
                    ftp.close()
                except:
                    print "Error closing FTP connection ..."

                print "FTP Download complete .."

                # Adjust permissions , change 33 to whatever GID/UID you need
                os.chown(rootdir + "/wp-content/uploads/treb/" + mlsnumber, userperm, groupperm)
                for root, dirs, files in os.walk(rootdir + "/wp-content/uploads/treb/" + mlsnumber):
                    for filename in files:
                            os.chown(os.path.join(root, filename), userperm, groupperm)

                # Set featured image
                featured_filename = rootdir + "/wp-content/uploads/treb/" + mlsnumber + "/" + mlsnumber + ".jpg"
                if os.path.isfile(featured_filename):
                    featured_data = {
                    'name': mlsnumber + ".jpg",
                    'type': 'image/jpeg',
                    }
                    try:
                        with open(featured_filename, 'rb') as img:
                            featured_data['bits'] = xmlrpc_client.Binary(img.read())
                            response = wp.call(media.UploadFile(featured_data))
                            attachment_id = response['id']
                            #Output text to a post file to be eventually posted to wordpress
                            template_out = open(cur_path + "/metadata/" + mlsnumber + "_post.txt", "w")
                            template_out.write(post.content)
                            template_out.close()
                            post.id = wp.call(NewPost(post))
                            if attachment_id:
                                post.thumbnail = attachment_id
                    except Exception as e:
                        print('*** Caught exception: %s: %s' % (e.__class__, e))
                else: 
                    print "Featured image filename not found, skipping this listing.."
                    continue
    
                # Set post to publish
                post.post_status = 'publish'
                wp.call(posts.EditPost(post.id, post))
                post_link = wp.call(posts.GetPost(post.id))

                # Post to twitter
                if tw_enabled == "true":
                    print "Posting to twitter .."
                    auth = tweepy.OAuthHandler(tw_consumer, tw_secret)
                    auth.set_access_token(tw_token, tw_token_secret)
                    api = tweepy.API(auth)
                    tweet = 'New Listing : ' + str(addressfix) + ' , ' + str(listpricefix) + ' , ' + str(bedrooms) + ' beds ' + str(bathrooms) + ' baths ' + '#' + str(mlsnumber) + ' '
                    hashtag_list = tw_hashtags.split(',')
                    for hash in hashtag_list:
                        tweet = str(tweet) + '#' + str(hash) + ' '
                    tweet_fixed = ''.join(str(e) for e in tweet)
                    tweet_url = post_link.link 
                    tweet_fixed += ' ' + str(tweet_url)
                    try: 
                        api.update_status(tweet_fixed[:280])
                    except Exception, e:
                        print 'Twitter error : ' + str(e)
    finally:
        f.close() #cleanup
        silentremove(outfile)
    
    # Unavailable option
elif avail_opt == "unavail" :

    # read the csv file
    f = open(outfile, 'r') #open file
    try:
        r = csv.reader(f) #init csv reader
        r.next()
        wp = wordpress_xmlrpc.Client(wp_url,wp_username,wp_password,transport=SpecialTransport())
        for row in r:
            mlsnumber = row[0]
            # Prepare post title for search
            unavail_id = unlist_mls(mlsnumber)
            if unavail_id : 
                print "The following post has been unpublished : " + mlsnumber 
            else:
                print "No matches for any posts with the MLS " + mlsnumber

    finally:
        f.close() #cleanup

else :
    print "Invalid command options given"
    sys.exit(0)
