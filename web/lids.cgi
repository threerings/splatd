#!/usr/bin/env python
# lids.cgi vi:ts=4:sw=4:expandtab:
#
# LDAP Information Distribution Suite
# Author: Will Barton <wbb4@opendarwin.org>
#
# Copyright (c) 2005 Three Rings Design, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright owner nor the names of contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import cgi, cgitb, Cookie
import sys, traceback, os.path

cgitb.enable()
sys.path.append("/Users/will/Projects/ThreeRings/lids/")

import lids
from session import Session, SessionError

TEMPLATES="./"
CONFIG="../lids.conf"
SECTIONS=["sshPublicKeys",]
SCRIPTNAME = os.path.basename(sys.argv[0])

TMPDIR="/tmp"
SESSION = None

def output_text(text):
    template = open(TEMPLATES + "lids_template.templ").read()
    print "Content-type: text/html\n\n"
    print template % {'content':text,}
    #'session':SESSION["id"]}

def _error(text):
    et = open(TEMPLATES + "lids_error.templ").read()
    return et % {'error':text}

def _get_entry(conf, base_dn, user):
    entry = lids.search(conf, None, base_dn, 
            "uid=" + user )[0]
    return entry

def _get_sections(conf, entry_dn):
    matched_sections = []
    for section in SECTIONS:
        if (section + ".search_base") in conf.keys():
            sbase = conf.get(section + ".search_base")
            if entry_dn.find(sbase) != -1:
                matched_sections.append(section)
    return matched_sections

def _get_fields(conf, sections, entry):
    fields = {}
    for section in sections:
        fs = lids.helper_attributes(conf, section, entry)
        ## XXX: there's a better way to merge contents of lists
        for f in fs: fields[f] = fs[f]
    return fields

def _get_session_cookie():
    if os.environ.has_key('HTTP_COOKIE'):
        c = Cookie.SimpleCookie(os.environ['HTTP_COOKIE'])
        return c.get('SESSION').value
    return None
        

# Binds as a username and password that are stored in the current
# session.  
def _checkauth():
    global SESSION
    conf = lids.parse_config(CONFIG)
    base_dn = conf['ldap.base_dn']

    if not SESSION.has_key("username") or not SESSION.has_key("password"):
        #SESSION.destroy()
        raise ValueError, "Session doesn't contain authentication data"

    try:
        # XXX: This is a bad way to get the uid's dn 
        entry = _get_entry(conf, base_dn, SESSION["username"])
        entry_dn = entry.getAttribute("dn")
    except:
        raise SessionError("User DN does not exist")
    
    try:
        lids.bind(conf, entry_dn, SESSION["password"])
        if not _get_session_cookie():
            c = Cookie.SimpleCookie()
            c["SESSION"] = SESSION["id"]
            print c
    except lids.LIDSError:
        # if it failed, destroy the session
        SESSION.destroy()
        raise SessionError, "Unable to bind as user"

# This function displays the login page, or passes through if the user
# is authenticated
def authenticate():
    ## So that we can modify it
    global SESSION
    error = ""
    conf = lids.parse_config(CONFIG)

    # Check for a session cookie
    s = _get_session_cookie()
    if s:
        try:
            SESSION = Session(id = s, tempdir = TMPDIR)
            _checkauth()
            return 
        except SessionError, e:
            error = _error("Session authentication failed:" + str(e))
        #except ValueError:
        #    error = _error("noooo")
        #    pass
   
    # Otherwise, check for a form submission
    form = cgi.FieldStorage()
    if form.has_key("username") and form.has_key("password"): 
        try:
            SESSION = Session(tempdir = TMPDIR)
            SESSION["username"] = form.getvalue("username")
            SESSION["password"] = form.getvalue("password")
            _checkauth()
            return True
        except SessionError, e:
            error = _error("Username or password invalid: " + str(e))

    authform = open(TEMPLATES + "lids_authform.templ").read()
    adict = {
            'username':form.getvalue("username", ""),
            'password':form.getvalue("password", ""),
            'error':error,
            'script':SCRIPTNAME,
            }
    output_text(authform % adict)
    sys.exit()

def update_form():
    
    ## Get the configuration
    conf = lids.parse_config(CONFIG)
    
    # Check to see if the form was submitted, if it was, return
    # and drop through to update()
    form = cgi.FieldStorage()
    if form.has_key("update"):
        return

    # Otherwise, print the form.
    ## Get the base dn for this user
    base_dn = conf['ldap.base_dn']
    entry = _get_entry(conf, base_dn, SESSION["username"])
    entry_dn = entry.getAttribute("dn")

    ## Load the form template
    updateForm = open(TEMPLATES + "lids_updateform.templ").read()
    
    ## Match the entry_dn to the search_base of the conf sections
    matched_sections = _get_sections(conf, entry_dn)
    
    ftext = ""
    fields = _get_fields(conf, matched_sections, entry)
    ## Create form elements for each field
    for field in fields:
        if len(fields[field]) > 20:
            ftext += """
                <p>%(field)s:<br/>
                    <textarea rows="8" cols="60" 
                        name="%(field)s">%(value)s</textarea>
                </p>
                """ % {'field':field, 'value':fields[field]}
        else:
            ftext += """
                <p>%(field)s:
                    <input type="text" name="%(field)s"
                        value="%(value)s"/></p>
                """ % {'field':field, 'value':fields[field]}

    ## Output the form
    # XXX: Provide easier access to the generic user info to the
    # template
    odict = {
        'fields':ftext, 
        'script':SCRIPTNAME,
        'username':entry.getAttribute("uid"),
        'givenName':entry.getAttribute("givenName"),
        'sn':entry.getAttribute("sn"),
        }
    output_text(updateForm % odict)
    sys.exit()

def update():
    ## Get the configuration
    conf = lids.parse_config(CONFIG)
    base_dn = conf['ldap.base_dn']

    ## Get the base dn for this user
    entry = _get_entry(conf, base_dn, SESSION["username"])
    entry_dn = entry.getAttribute("dn")
 
    ## Gather the submitted fields
    form = cgi.FieldStorage()
    matched_sections = _get_sections(conf, entry_dn)
    fields = _get_fields(conf, matched_sections, entry)

    ## Create a dictionary of values
    fdict = {}
    for field in fields:
        fdict[field] = form.getvalue(field)

    ## call lids.modify
    # XXX: Use user bind
    lids.modify(conf, base_dn, fdict) #, entry_dn, SESSION["password"])

    ## Print a success message?
    output_text("<p><b>Information successfully updated.</b></p>")

if __name__ == "__main__":
    try:
    	authenticate()
        update_form()
        update()
    except SystemExit:
        pass
    # cgitb takes care of this
    #except:
    #    sys.stderr = sys.stdout
    #    print "Content-type: text/plain\n\n"
    #    traceback.print_exc()
