TREB Wordpress Python Integration
=================================

Managed Hosting Services : [Stackstar](https://www.stackstar.com)

Web Design and Development Services : [Toronto Web Development](https://shift8web.ca)


This python code fully integrates and automates the integration of Toronto Real Estate Board Listing data into your wordpress blog. There are many 3rd party libraries integrated into this python code, most importantly the wordpress_xmlrpc python library, available here :

https://github.com/maxcutler/python-wordpress-xmlrpc


Installation and Integration Instructions
=========================================

Integrating and installation instructions for this python code can be found here :

[Integrate Wordpress and TREB real estate listings](https://shift8web.ca/2013/07/treb-idx-wordpress-integration/)

Listing Template
================

The listing_template.txt has been updated to utilize shortcode for WP Bakery's Visual Composer

Images
======

Images with TREB (TRREB) used to be accessible by a centralized FTP server. This was retired at the end of 2022 and access for listing photos moved to a [RETS feed](https://en.wikipedia.org/wiki/Real_Estate_Transaction_Standard). This was integrated and tested with the TREB RETS feed using a python RETS client library. The result is an adjustment to the config file to accommodate the RETS username, password and URL. This system largely operates the same way it did with FTP albeit much faster than FTP which is an added bonus.

Google Map
==========

You should set up a google map api key and define it in your treb config file now. The code is dynamically generated


TO-DO Items
===========

Still to do :

	- Better error checking , syntax error checking of option variables

