#!/usr/bin/env python
# test_opennms.py vi:ts=4:sw=4:expandtab:
#
# Author: Landon Fuller <landonf@threerings.net>
#
# Copyright (c) 2006 - 2007 Three Rings Design, Inc.
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

""" OpenNMS Unit Tests """

from twisted.trial import unittest

import ldap
import time
import os, stat
import tempfile
import shutil

import splat
from splat import plugin
from splat.ldaputils import client as ldapclient
from splat.ldaputils.test import slapd

from splat.helpers import opennms

# Useful Constants
from splat.helpers.test import DATA_DIR
TEST_USER = "joe"
TEST_GROUP = "Admin"

USERS_FILE = os.path.join(DATA_DIR, "opennms-users.xml")
GROUPS_FILE = os.path.join(DATA_DIR, "opennms-groups.xml")

# Test Cases
class PluginTestCase(unittest.TestCase):
    """ Test Splat SSH Helper """
    def _mkstempTestFile (self, inputPath):
        # Set up the (temporary) file copy
        (outputFD, outputPath) = tempfile.mkstemp()
        inputFile = open(inputPath)
        outputFile = os.fdopen(outputFD, 'w')
        shutil.copyfileobj(inputFile, outputFile)
        inputFile.close()
        outputFile.close()

        # World-readable
        os.chmod(outputPath, 0644)

        return outputPath

    def setUp(self):
        self.usersFile = self._mkstempTestFile(USERS_FILE)
        self.groupsFile = self._mkstempTestFile(GROUPS_FILE)

        # Set up the plugin
        self.options = {
            'usersfile'         : self.usersFile,
            'groupsfile'        : self.groupsFile,
            'opennmsgroup'      : 'Accounting',
            'usernameattribute' :'uid',
            'fullnameattribute' : 'cn',
            'emailattribute'    : 'mail'
        }

        self.slapd = slapd.LDAPServer()
        self.conn = ldapclient.Connection(slapd.SLAPD_URI)
        self.hc = plugin.HelperController('test', 'splat.helpers.opennms', 5, 'dc=example,dc=com', '(objectClass=sshAccount)', False, self.options)
        self.entries = self.conn.search(self.hc.searchBase, ldap.SCOPE_SUBTREE, self.hc.searchFilter, self.hc.searchAttr)

        # We test that checking the modification timestamp on entries works in
        # plugin.py's test class, so just assume the entry is modified here.
        self.modified = True

    def tearDown(self):
        os.unlink(self.usersFile)
        os.unlink(self.groupsFile)
        self.slapd.stop()

    def test_valid_options(self):
        """ Test Parsing of Valid Options """
        assert self.hc.helperClass.parseOptions(self.options)

    def test_invalid_option(self):
        """ Test Invalid Option """
        self.options['foo'] = 'bar'
        self.assertRaises(splat.SplatError, self.hc.helperClass.parseOptions, self.options)
    
    def test_missing_option (self):
        # Missing options
        del self.options['usernameattribute']
        self.assertRaises(splat.SplatError, self.hc.helperClass.parseOptions, self.options)
        
    def test_context(self):
        """ Test Context Consistency With Options """
        context = self.hc.helperClass.parseOptions(self.options)
        self.assertEquals(context.attrmap[opennms.OU_USERNAME], 'uid')
        self.assertEquals(context.attrmap[opennms.OU_FULLNAME], 'cn')

    def test_work(self):
        context = self.hc.helperClass.parseOptions(self.options)
        plugin = self.hc.helperClass()
        for entry in self.entries:
            plugin.work(context, entry, True)
        plugin.finish()

        # Verify that new users were added, old users deleted
        userdb = opennms.Users(self.usersFile)
        self.assertNotEqual(userdb.findUser("john"), None)
        self.assertEqual(userdb.findUser("admin"), None)

        fstat = os.stat(self.usersFile)
        self.assertEqual(stat.S_IMODE(fstat.st_mode), 0644)

        # Verify that new groups were created, old groups deleted
        groupdb = opennms.Groups(self.groupsFile)
        self.assertNotEqual(groupdb.findGroup("Accounting"), None)
        self.assertEqual(groupdb.findGroup("admin"), None)

        fstat = os.stat(self.groupsFile)
        self.assertEqual(stat.S_IMODE(fstat.st_mode), 0644)

class UsersTestCase (unittest.TestCase):
    """ Test OpenNMS User Handling """
    
    def setUp (self):
        #self.slapd = slapd.LDAPServer()
        #self.conn = ldapclient.Connection(slapd.SLAPD_URI)
        self.users = opennms.Users(USERS_FILE)

    def tearDown (self):
        #self.slapd.stop()
        pass

    def test_findUser (self):
        user = self.users.findUser(TEST_USER)
        self.assertEquals(user.find("user-id").text, TEST_USER)

    def test_createUser (self):
        self.users.deleteUser(TEST_USER)
        user = self.users.createUser(TEST_USER, comments="hello")
        self.users.updateUser(user, fullName="testname")

        user = self.users.findUser(TEST_USER)
        self.assertEquals(user.find("full-name").text, "testname")
        self.assertEquals(user.find("user-comments").text, "hello")

        self.users.updateUser(user, email="test@email")
        email = self.users._findUserContact(user, "email")
        self.assertEquals(email.get("info"), "test@email")

    def test_updateUser (self):
        user = self.users.findUser(TEST_USER)
        self.users.updateUser(user, fullName="testname", email="test@email", xmppAddress="joe", numericPager="555",
            numericPagerService = "Monopoly")
    
        user = self.users.findUser(TEST_USER)
        self.assertEquals(user.find("full-name").text, "testname")

        email = self.users._findUserContact(user, "email")
        self.assertEquals(email.get("info"), "test@email")

        pager = self.users._findUserContact(user, "numericPage")
        self.assertEquals(pager.get("info"), "555")
        self.assertEquals(pager.get("serviceProvider"), "Monopoly")
        
        xmpp = self.users._findUserContact(user, "xmppAddress")
        self.assertEquals(xmpp.get("info"), "joe")

    def test_getUsers (self):
        users = self.users.getUsers()
        self.assertEquals(len(users), 3)

class GroupsTestCase (unittest.TestCase):
    """ Test OpenNMS User Handling """

    def setUp (self):
        self.groups = opennms.Groups(GROUPS_FILE)

    def test_findGroup (self):
        group = self.groups.findGroup(TEST_GROUP)
        self.assertEquals(group.find("user").text, "admin")

    def test_createGroup (self):
        group = self.groups.createGroup("newgroup", comments="hello")
        self.assertEquals(group.find("name").text, "newgroup")
        self.assertEquals(group.find("comments").text, "hello")

    def test_deleteGroup (self):
        group = self.groups.createGroup("newgroup", comments="hello")
        self.assert_(self.groups.findGroup("newgroup") != None)
        self.groups.deleteGroup("newgroup")
        self.assertEquals(self.groups.findGroup("newgroup"), None)

    def test_setMembers (self):
        group = self.groups.findGroup(TEST_GROUP)
        self.groups.setMembers(group, ('fred', 'joe', 'john'))

        # Make sure all the users are there
        users = group.findall("./user")
        self.assertEquals(len(users), 3)
        found = 0
        for user in users:
            if (user.text == "fred"):
                found += 1

            if (user.text == "joe"):
                found += 1

            if (user.text == "john"):
                found += 1

        self.assertEquals(found, 3)
