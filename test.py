#!/usr/bin/python

import urllib

the_string = "https://www.thepropertyteam.ca/wp-content/uploads/treb/whatever/123.jpg"

print urllib.quote_plus(the_string)
