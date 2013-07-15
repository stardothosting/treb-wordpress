#!/usr/bin/python
# TREB wordpress listing import script

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


import csv, sys, urllib, urlparse, string, time, locale, os, os.path, socket, re, requests, xmlrpclib
import wordpresslib
import configparser
from datetime import date, timedelta
from ftplib import FTP
from googlemaps import GoogleMaps
from tempfile import mkstemp
from shutil import move
from wordpress_xmlrpc import *
from wordpress_xmlrpc.methods.posts import *
from wordpress_xmlrpc.methods.users import *

# Read configuration file parameters
Config = ConfigParser.ConfigParser()
Config.read("~/.treb_wordpress")

# Check command arguments
#if len(sys.argv) <= 6 :
#        print "\nUsage Syntax :"
#        print "\ntreb_fetch.py [option1] [option2] [option3] [username] [password] [rootdir]"
#        print "Option 1 : \"avail\" \"unavail\" , processes available or unavailable listings"
#        print "Option 2 : \"NNNNNNN\" , MLS Agent ID number (7 digits)"
#        print "Option 3 : Number of days prior to gather listing data"
#        print "Username : TREB username for downloading listings"
#        print "Password : TREB password for downloading listings"
#        print "Root Dir : specifcy the root directory of the site, for interatction with wordpress, no trailing slash\n\n"
#	sys.exit(0)

if len(sys.argv) <= 1 :
        print "\nUsage Syntax :"
        print "\ntreb_fetch.py [option1] [option2]"
        print "Option 1 : \"avail\" \"unavail\" , processes available or unavailable listings"
        print "Option 2 : Number of days prior to gather listing data"
        sys.exit(0)

# Get Connection and Authentication  config data
wp_url = ConfigSectionMap("wordpress")['wp_url']
wp_username = ConfigSectionMap("wordpress")['wp_username']
wp_password = ConfigSectionMap("wordpress")['wp_password']
user = ConfigSectionMap("treb")['trebuser']
password = ConfigSectionMap("treb")['trebpass']
agent_id = ConfigSectionMap("treb")['agent_id']
int_date = ConfigSectionMap("treb")['num_days']
rootdir = ConfigSectionMap("treb")['root_dir']

###################
# Functions START #
###################

def ftpget( hostname, localpath, remotepath, filename ) :

        # Go to destination DIR
        os.chdir(localpath)

        # FTP Details
        ftp = FTP(hostname)
        ftp.login(user + "@photos", password)

        ftp.cwd(remotepath)
        ftp.sendcmd("TYPE i")
        f = open(filename,"wb")
        try:
                ftp.retrbinary("RETR " + filename,f.write)
        except:
                print "File not found.. exiting .."
                os.remove(filename)
        try:
                ftp.close()
        except:
                print "Error closing FTP connection ..."

#Searches wordpress posts based on title
def find_id(title):

	offset = 0
	increment = 10
	while True:
		filter = { 'offset' : offset }
		p = wp.call(GetPosts(filter))
		if len(p) == 0:
			break # no more posts returned
		for post in p:
			if post.title == title:
				return(post.id)
		offset = offset + increment
	return(False)

#Take text and replace words that match an array
def replace_words(text, word_dic):
	rc = re.compile('|'.join(map(re.escape, word_dic)))
	def translate(match):
		return word_dic[match.group(0)]
	return rc.sub(translate, text)

#################
# Functions END #
#################
	
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
	print rootdir

# build the url query string
url = "http://3pv.torontomls.net/data3pv/DownLoad3PVAction.asp?user_code=" + user + "&password=" + password + "&sel_fields=*&dlDay=" + the_day + "&dlMonth=" + the_mon + "&dlYear=" + the_yr + "&order_by=&au_both=avail&dl_type=file&incl_names=yes&use_table=MLS&send_done=no&submit1=Submit&query_str=lud%3E%3D%27" + the_yr + the_mon + the_day + "%27"

# retrieve URL and  write results to filename
#filename = "out_py.txt"
#urllib.urlretrieve(url,filename)


# read the csv file
f = open('../out_py.txt', 'r') #open file
try:
    r = csv.reader(f) #init csv reader
    r.next()
    for row in r:
        description = row[2]
        streetname = row[273]
        streetnumber = row[275]
	streetsuffix = row[276]
	address = row[3]
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

	#Sanitize Variables
	listpricefix = locale.currency(int(listprice), grouping=True )
#	description = description.replace(":", "\:").replace("/", "\/").replace("&", "\&")
#	virtualtour = virtualtour.replace(":", "\:").replace("/", "\/").replace("&", "\&")

	# Set category and verify if other agent listing is over $600,0000
	if agentid == agent_id:
                listingcategory = "Listings"
        else:
		if int(listprice) < 600000:
                        print "Listing is below $600,000 - Not adding"
                        continue
                else:
                        listingcategory = "OtherListings"

        # Get the latitude + longitude variables
	gmaps = GoogleMaps()
	lat, lng = gmaps.address_to_latlng(address + " Toronto, Ontario, Canada")
	lat = str(lat)
	lng = str(lng)

        # Set variable for virtual tour
	if virtualtour == "":
		virtualtour = "N/A"
	else:
		virtualtour = "<a href=\"" + virtualtour + "\" target=\"_new\"><b>Click here for virtual tour</b></a>"

	# Start prepping the uploads folder for the MLS listing images
	if pictures == "Y":
		mlsimage = mlsnumber[-3:]
		print "MLS Image : " + mlsimage

		# Create upload folder if it doesnt exist
		if not os.path.exists(rootdir + '/wp-content/uploads/treb/' + mlsnumber):
    			os.makedirs(rootdir + '/wp-content/uploads/treb/' + mlsnumber)

		# GET The image files via FTP
	#	ftpget( "3pv.torontomls.net", rootdir + "/wp-content/uploads/treb/" + mlsnumber, "mlsmultiphotos/1/" + mlsimage, mlsnumber + ".jpg")
	#	ftpget( "3pv.torontomls.net", rootdir + "/wp-content/uploads/treb/" + mlsnumber, "mlsmultiphotos/2/" + mlsimage, mlsnumber + "_2.jpg")
	#	ftpget( "3pv.torontomls.net", rootdir + "/wp-content/uploads/treb/" + mlsnumber, "mlsmultiphotos/3/" + mlsimage, mlsnumber + "_3.jpg")
	#	ftpget( "3pv.torontomls.net", rootdir + "/wp-content/uploads/treb/" + mlsnumber, "mlsmultiphotos/4/" + mlsimage, mlsnumber + "_4.jpg")
	#	ftpget( "3pv.torontomls.net", rootdir + "/wp-content/uploads/treb/" + mlsnumber, "mlsmultiphotos/5/" + mlsimage, mlsnumber + "_5.jpg")
	#	ftpget( "3pv.torontomls.net", rootdir + "/wp-content/uploads/treb/" + mlsnumber, "mlsmultiphotos/6/" + mlsimage, mlsnumber + "_6.jpg")
	#	ftpget( "3pv.torontomls.net", rootdir + "/wp-content/uploads/treb/" + mlsnumber, "mlsmultiphotos/7/" + mlsimage, mlsnumber + "_7.jpg")
	#	ftpget( "3pv.torontomls.net", rootdir + "/wp-content/uploads/treb/" + mlsnumber, "mlsmultiphotos/8/" + mlsimage, mlsnumber + "_8.jpg")
	#	ftpget( "3pv.torontomls.net", rootdir + "/wp-content/uploads/treb/" + mlsnumber, "mlsmultiphotos/9/" + mlsimage, mlsnumber + "_9.jpg")
		
		# Adjust permissions , change 33 to whatever GID/UID you need
		os.chown(rootdir + "/wp-content/uploads/treb/" + mlsnumber, 33, 33)
		for root, dirs, files in os.walk(rootdir + "/wp-content/uploads/treb/" + mlsnumber):
			for filename in files:
				os.chown(os.path.join(root, filename), 33, 33)
        else:
                print "No photos ..."

        # Generate post content from the template file
	template_read = open("/usr/local/bin/treb/python/listing_template.txt", "r")
	template_text = template_read.read()
	template_read.close()

	#Replacements from the template
	reps = {'%STREETNUMBER%':streetnumber, '%STREETNAME%':streetname + ' ' + streetsuffix, '%POSTALCODE%':postalcode, '%LISTPRICE%':listpricefix, '%MLSNUMBER%':mlsnumber, '%BATHROOMS%':bathrooms, '%BEDROOMS%':bedrooms, '%SQFOOTAGE%':squarefoot, '%DESCRIPTION%':description, '%VIRTUALTOUR%':virtualtour}

	# Check if the post exists first
	wp = Client(wp_url,wp_username,wp_password)
	post = WordPressPost()
	post.title = address
	post.content = replace_words(template_text, reps)
	post.terms_names = {
        'post_tag': [mlsnumber],
        'category': ['My Child Category'],
	}
	#post_id = find_id(post.title)
	#if post_id:
	#	print "Sorry, a post ID exists already with that title: ", post_id
	#else:
	
	#wp.call(NewPost(post))


	#Output text to a post file to be eventually posted to wordpress	
	template_out = open("/usr/local/bin/treb/python/treb-wordpress/metadata/" + mlsnumber + "_post.txt", "w")
	template_out.write(template_replaced)
	template_out.close()

        # If there's a sold date then just set the sold flag to 1
        #if [ "$solddate" = "" ]
        #then
                # Create posts or modify existing posts
        #        /usr/bin/python $script_home/blogpost.py post $script_home/metadata/"$mlsnumber"_post.txt -U -d html --title="$streetnumber $streetname , Toronto" --categories="$listingcategory"

        #else
                # Create posts or modify existing posts
        #        /usr/bin/python $script_home/blogpost.py post $script_home/metadata/"$mlsnumber"_post.txt -U -d html --title="[SOLD!] $streetnumber $streetname , Toronto" --categories="$listingcategory"

        #fi


finally:
    f.close() #cleanup


