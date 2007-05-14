# opennms.py vi:ts=4:sw=4:expandtab:
#
# Support functions for plugins that deal with OpenNMS.
# Author: Landon Fuller <landonf@threerings.net>
#
# Copyright (c) 2007 Three Rings Design, Inc.
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

import os, tempfile

from splat import plugin

# Import cElementTree
try:
    # Python 2.5 cElementTree
    from xml.etree import cElementTree as ElementTree
except ImportError:
    # Stand-alone pre-2.5 cElementTree
    import cElementTree as ElementTree

from pysqlite2 import dbapi2 as sqlite

# XML Namespaces
XML_USERS_NAMESPACE = "http://xmlns.opennms.org/xsd/users"
XML_GROUPS_NAMESPACE = "http://xmlns.opennms.org/xsd/groups"

# OpenNMS User Record Fields
OU_USERNAME     = 'userName'
OU_FULLNAME     = 'fullName'
OU_COMMENTS     = 'comments'
OU_EMAIL        = 'email'
OU_PAGER_EMAIL  = 'pagerEmail'
OU_XMPP_ADDRESS = 'xmppAddress'
OU_NUMERIC_PAGER            = 'numericPager'
OU_NUMERIC_PAGER_SERVICE    = 'numericPagerService'
OU_TEXT_PAGER           = 'textPager'
OU_TEXT_PAGER_SERVICE   = 'textPagerService'
OU_LDAP_DN      = 'ldapDN'

class UserExistsException (plugin.SplatPluginError):
    pass

class NoSuchUserException (plugin.SplatPluginError):
    pass

class GroupExistsException (plugin.SplatPluginError):
    pass

class NoSuchGroupException (plugin.SplatPluginError):
    pass

class WriterContext(object):
    def __init__(self):
        # A map of (XML/database) fields to LDAP attributes
        # The name choices are no accident -- they're meant
        # to match between the DB and the XML.
        self.attrmap = {
            OU_USERNAME      : None,
            OU_FULLNAME      : None,
            OU_COMMENTS      : None,
            OU_EMAIL         : None,
            OU_PAGER_EMAIL    : None,
            OU_XMPP_ADDRESS   : None,
            OU_NUMERIC_PAGER  : None,
            OU_NUMERIC_PAGER_SERVICE    : None,
            OU_TEXT_PAGER     : None,
            OU_TEXT_PAGER_SERVICE  : None
        }

class Writer(plugin.Helper):
    @classmethod
    def attributes(self): 
        # We want all attributes
        return None

    @classmethod
    def parseOptions(self, options):
        context = WriterContext()

        for key in options.iterkeys():
            # Do some magic to check for 'attribute keys' without enumerating
            # them all over again.
            if (key.endswith("Attribute")):
                attrKey = key[:len(key) - len("Attribute")]
                if (context.attrmap.has_key(attrKey)):
                    context.attrmap[attrKey] = options[key]
                    continue

            raise plugin.SplatPluginError, "Invalid option '%s' specified." % key
            
        return context

    def _initdb (self, dbfile):
        """
        Create our temporary user record database
        """
        # Connect to the database
        self.db = sqlite.connect(dbfile)

        # Initialize the users table
        self.db.execute(
            """
            CREATE TABLE Users (
                userName        TEXT NOT NULL PRIMARY KEY,
                ldapDN          TEXT NOT NULL,
                fullName        TEXT DEFAULT NULL,
                comments        TEXT DEFAULT NULL,
                email           TEXT DEFAULT NULL,
                pagerEmail      TEXT DEFAULT NULL,
                numericPager    TEXT DEFAULT NULL,
                numericPagerService TEXT DEFAULT NULL,
                textPager       TEXT DEFAULT NULL,
                textPagerService    TEXT DEFAULT NULL
            );
            """
        )

        # Now for the group table
        self.db.execute(
            """
            CREATE TABLE Groups (
                groupName   TEXT NOT NULL PRIMARY KEY,
                comments    TEXT DEFAULT NULL
            );
            """
        )

        # ... finally, the group member table
        self.db.execute(
            """
            CREATE TABLE GroupMembers (
                groupName   TEXT NOT NULL,
                userName    TEXT NOT NULL,
                PRIMARY KEY(groupName, username),
                FOREIGN KEY(groupName) REFERENCES Groups(groupName)
                FOREIGN KEY(userName) REFERENCES Users(userName)
            );
            """
        )

        # Drop the file out from under ourselves
        os.unlink(dbfile)

        # Commit our changes
        self.db.commit()

    def __init__ (self):
        # If a fatal error occurs, set this to True, and we won't attempt to
        # overwrite any files in finish()
        self.fatalError = False

        # Create a temporary database in which to store user records
        dbfile = None
        try:
            (handle, dbfile) = tempfile.mkstemp()
            self._initdb(dbfile)
        except Exception, e:
            if (dbfile != None and os.path.exists(dbfile)):
                os.unlink(dbfile)
            raise plugin.SplatPluginError("Initialization failure: %s" % e)

    def _insertDict(self, table, dataDict):
        """
        Safely (ith SQL escaping) insert a dict into a table
        """ 
        def dictValuePad(key):
            return '?'
        
        cols = []
        vals = []

        for key in dataDict.iterkeys():
            cols.append(key)
            vals.append(dataDict[key])

        sql = 'INSERT INTO ' + table
        sql += ' ('
        sql += ', '.join(cols)
        sql += ') VALUES ('
        sql += ', '.join(map(dictValuePad, vals))
        sql += ');'

        self.db.execute(sql, vals)

    def _createUserAttributeDict (self, ldapEntry, attrMap):
        """
        Add to dict from attribute dictionary
        """
        result = {}

        # Add required elements
        result[OU_USERNAME] = ldapEntry.attributes[attrMap[OU_USERNAME]][0]
        result[OU_LDAP_DN] = ldapEntry.dn

        # Add optional elements
        for key in attrMap.iterkeys():
            ldapKey = attrMap[key]
            if (ldapEntry.attributes.has_key(ldapKey)):
                result[key] = ldapEntry.attributes[ldapKey][0]

        return result

    def work (self, context, ldapEntry, modified):
        # Validate the available attributes
        attributes = ldapEntry.attributes
        if (not attributes.has_key(context.attrmap[OU_USERNAME])):
            raise plugin.SplatPluginError, "Required attribute %s not found for dn %s." % (context.attrmap[OU_USERNAME], ldapEntry.dn)

        # Add required fields to the database
        #insertData = {
        #    "userName" : attrs[ctx.usernameAttr][0],
        #    "ldapDn" : ldapEntry.dn
        #}

        """
        CREATE TABLE Users (
            userName        TEXT NOT NULL PRIMARY KEY,
            ldapDN          TEXT NOT NULL,
            fullName        TEXT DEFAULT NULL,
            comments        TEXT DEFAULT NULL,
            email           TEXT DEFAULT NULL,
            pagerEmail      TEXT DEFAULT NULL,
            numericPager    TEXT DEFAULT NULL,
            numericPagerService TEXT DEFAULT NULL,
            textPager       TEXT DEFAULT NULL,
            textPagerService    TEXT DEFAULT NULL
        );
        """

        insertData = self._createUserAttributeDict(ldapEntry, context.attrmap)
        
        try:
            self._insertDict("Users", insertData)
            self.db.commit()
        except Exception, e:
            self.fatalError = True
            raise plugin.SplatPluginError, "Failed to commit user record to database for dn %s: %s" % (ldapEntry.dn, e)

class Users (object):
    def __init__ (self, path):
        self.doc = ElementTree.ElementTree(file = path)

    def findUser (self, username):
        for entry in self.doc.findall("./{%s}users/*" % (XML_USERS_NAMESPACE)):
            userId = entry.find("user-id")
            if (userId != None and userId.text == username):
                return entry

        # Not found
        return None

    def _getUsers (self):
        return self.doc.find("./{%s}users" % (XML_USERS_NAMESPACE))

    @classmethod
    def _setChildElementText (self, parentNode, nodeName, text):
        node = parentNode.find(nodeName)
        node.text = text

    @classmethod
    def _setContactInfo (self, parentNode, contactType, info, serviceProvider = None):
        node = self._findUserContact(parentNode, contactType)

        node.set("info", info)
        if (serviceProvider != None):
            node.set("serviceProvider", serviceProvider)

    @classmethod
    def _findUserContact (self, parentNode, contactType):
        nodes = parentNode.findall("./{%s}contact" % (XML_USERS_NAMESPACE))
        for node in nodes:
            if (node.get("type") == contactType):
                return node

        return None

    def deleteUser (self, username):
        user = self.findUser(username)
        if (self.findUser == None):
            raise NoSuchUserException("Could not find user %s." % username)

        users = self._getUsers()
        users.remove(user)

    def createUser (self, username, fullName = "", comments = "", password = "XXX"):
        """
        Insert and return a new user record.
        @param username User's login name
        @param fullName User's full name.
        @param comments User comments.
        @param password User's password (unused if LDAP auth is enabled)
        """

        if (self.findUser(username) != None):
            raise UserExistsException("User %s exists." % username)

        # Create the user record
        user = ElementTree.SubElement(self._getUsers(), "user")

        # Set up the standard user data
        userId = ElementTree.SubElement(user, "user-id", xmlns="")
        userId.text = username

        fullName = ElementTree.SubElement(user, "full-name", xmlns="")
        fullName.text = fullName

        userComments = ElementTree.SubElement(user, "user-comments", xmlns="")
        userComments.text = comments

        userPassword = ElementTree.SubElement(user, "password", xmlns="")
        userPassword.text = password

        # Add the required (blank) contact records
        # E-mail
        ElementTree.SubElement(user, "contact", type="email", info="")

        # Pager E-mail
        ElementTree.SubElement(user, "contact", type="pagerEmail", info="")

        # Jabber Address
        ElementTree.SubElement(user, "contact", type="xmppAddress", info="")

        # Numeric Pager
        ElementTree.SubElement(user, "contact", type="numericPage", info="", serviceProvider="")

        # Text Pager
        ElementTree.SubElement(user, "contact", type="textPage", info="", serviceProvider="")

        return user

    def updateUser (self, user, fullName = None, comments = None, email = None,
        pagerEmail = None, xmppAddress = None, numericPager = None, textPager = None):
        """
        Update a user record.

        <user>
            <user-id xmlns="">admin</user-id>
            <full-name xmlns="">Administrator</full-name>
            <user-comments xmlns="">Default administrator, do not delete</user-comments>
            <password xmlns="">xxxx</password>
            <contact type="email" info=""/>
            <contact type="pagerEmail" info=""/>
            <contact type="xmppAddress" info=""/>
            <contact type="numericPage" info="" serviceProvider=""/>
            <contact type="textPage" info="" serviceProvider=""/>
        </user>

        @param user: User XML node to update.
        @param fullName: User's full name.
        @param comments: User comments.
        @param email: User's e-mail address.
        @param pagerEmail: User's pager e-mail address.
        @param xmppAddress: User's Jabber address.
        @param numericPager: User's numeric pager. (number, service) tuple.
        @param textPager: User's text pager. (number, service) tuple.
        """
        if (fullName != None):
            self._setChildElementText(user, "full-name", fullName)
        
        if (comments != None):
            self._setChildElementText(user, "user-comments", comments)

        if (email != None):
            self._setContactInfo(user, "email", email[0])

        if (pagerEmail != None):
            self._setContactInfo(user, "pagerEmail", pagerEmail[0], pagerEmail[1])

        if (xmppAddress != None):
            self._setContactInfo(user, "xmppAddress", xmppAddress[0])

        if (numericPager != None):
            self._setContactInfo(user, "numericPage", numericPager[0], numericPager[1])

        if (textPager != None):
            self._setContactInfo(user, "textPager", textPager[0], textPager[1])


class Groups (object):
    """
    <?xml version="1.0" encoding="UTF-8"?>
    <groupinfo xmlns="http://xmlns.opennms.org/xsd/groups"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="groupinfo">
        <ns1:header xmlns:ns1="http://xmlns.opennms.org/xsd/types">
            <rev xmlns="">1.3</rev>
            <created xmlns="">Monday, May 7, 2007 9:57:05 PM GMT</created>
            <mstation xmlns="">dhcp-219.internal.opennms.org</mstation>
        </ns1:header>
        <groups>
            <group>
                <name xmlns="">Admin</name>
                <comments xmlns="">The administrators</comments>
                <user xmlns="">admin</user>
                <user xmlns="">landonf</user>
            </group>
        </groups>
    </groupinfo>
    """
    def __init__ (self, path):
        self.doc = ElementTree.ElementTree(file = path)

    def findGroup (self, groupName):
        for entry in self.doc.findall("./{%s}groups/*" % (XML_GROUPS_NAMESPACE)):
            groupId = entry.find("name")
            if (groupId != None and groupId.text == groupName):
                return entry

        # Not found
        return None

    def _getGroups (self):
        return self.doc.find("./{%s}groups" % (XML_GROUPS_NAMESPACE))

    def createGroup (self, groupName, comments = ""):
        """
        Insert and return a new group record.
        @param groupName Group name.
        @param comments Group comments.
        """
        if (self.findGroup(groupName) != None):
            raise GroupExistsException("Group %s exists." % groupName)

        # Create the group record
        group = ElementTree.SubElement(self._getGroups(), "group")

        # Set up the standard group data
        groupId = ElementTree.SubElement(group, "name", xmlns="")
        groupId.text = groupName

        groupComments = ElementTree.SubElement(group, "comments", xmlns="")
        groupComments.text = comments

        return group

    def setMembers (self, group, members):
        """
        Set a groups' members.
        @param group Group XML node to update.
        @param members A list of member names.
        """
        # Delete existing user entries
        entries = group.findall("./user")
        for entry in entries:
            group.remove(entry)

        # Add new user entries
        for member in members:
            entry = ElementTree.SubElement(group, "user", xmlns="")
            entry.text = member