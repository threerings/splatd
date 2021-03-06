#!/usr/bin/env python
# test_plugin.py vi:ts=4:sw=4:expandtab:
#
# Scalable Periodic LDAP Attribute Transmogrifier
# Authors:
#       Landon Fuller <landonf@threerings.net>
#       Will Barton <wbb4@opendarwin.org>
#
# Copyright (c) 2005, 2006 Three Rings Design, Inc.
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

""" LDAP Unit Tests """

from twisted.trial import unittest

import ldap

import splat
from splat import plugin
from splat.ldaputils import client as ldapclient
from splat.ldaputils.test import slapd

# Useful Constants
from splat.test import DATA_DIR

# Test Cases
class MailForwardingAddresstestCase(unittest.TestCase):
    """ Test Splat Mail Forwarding Helper """
    def setUp(self):
        self.options = { 
            'home':'/home', 
            'minuid':'0', 
            'mingid':'0',
            'makehome':'true'
        }
        self.slapd = slapd.LDAPServer()
        self.conn = ldapclient.Connection(slapd.SLAPD_URI)
        self.hc = plugin.HelperController('test', 'splat.helpers.mailForwardingAddress', 5, 'dc=example,dc=com', '(objectClass=sshAccount)', False, self.options)
        self.entries = self.conn.search(self.hc.searchBase, ldap.SCOPE_SUBTREE, self.hc.searchFilter, self.hc.searchAttr)
        # We test that checking the modification timestamp on entries works in
        # plugin.py's test class, so just assume the entry is modified here.
        self.modified = True

    def tearDown(self):
        self.slapd.stop()

    def test_valid_options(self):
        """ Test Parsing of Valid Options """
        assert self.hc.helperClass.parseOptions(self.options)

    def test_invalid_option(self):
        """ Test Invalid Option """
        options = self.options
        options['foo'] = 'bar'
        self.assertRaises(splat.SplatError, self.hc.helperClass.parseOptions, options)

    def test_option_home(self):
        """ Test Home Directory Validation """
        options = { 
            'home':'/fred'
        }
        self.context = self.hc.helperClass.parseOptions(options)
        self.assertRaises(splat.SplatError, self.hc.helperClass().work, self.context, self.entries[0], self.modified)

    def test_option_minuid(self):
        """ Test UID Validation """
        options = { 
            'minuid':'9000000'
        }
        self.context = self.hc.helperClass.parseOptions(options)
        self.assertRaises(splat.SplatError, self.hc.helperClass().work, self.context, self.entries[0], self.modified)

    def test_option_mingid(self):
        """ Test GID Validation """
        options = { 
            'mingid':'9000000'
        }
        self.context = self.hc.helperClass.parseOptions(options)
        self.assertRaises(splat.SplatError, self.hc.helperClass().work, self.context, self.entries[0], self.modified)

    def test_context(self):
        """ Test Context Consistency With Options """
        context = self.hc.helperClass.parseOptions(self.options)
        self.assertEquals(context.makehome, True)

    def test_group_context(self):
        """ Test Group Context Consistency With Service Options """
        filter = ldapclient.GroupFilter(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(&(objectClass=groupOfUniqueNames)(cn=developers))', 'uniqueMember')
        self.hc.addGroup(filter)
        self.assertEquals(self.hc.groupsCtx[filter].makehome, True)
        self.assertEquals(self.hc.groupsCtx[filter].minuid, 0)

    def test_group_context_custom(self):
        """ Test Group Context Consistency With Group Specific Options """
        options = self.options
        # Run parseOptions here to make sure the options dictionary is not 
        # being modified by it.
        self.hc.helperClass.parseOptions(options)
        # Now update with a custom option for this group.
        options['minuid'] = '10'
        filter = ldapclient.GroupFilter(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(&(objectClass=groupOfUniqueNames)(cn=developers))', 'uniqueMember')
        self.hc.addGroup(filter, options)
        self.assertEquals(self.hc.groupsCtx[filter].minuid, 10)
        self.assertEquals(self.hc.groupsCtx[filter].mingid, 0)
        self.assertEquals(self.hc.groupsCtx[filter].makehome, True)
