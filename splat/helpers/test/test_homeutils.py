#!/usr/bin/env python
# test_homeutils.py vi:ts=4:sw=4:expandtab:
#
# Scalable Periodic LDAP Attribute Transmogrifier
# Author:
#       Nick Barkas <snb@threerings.net>
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

""" LDAP Unit Tests """

from twisted.trial import unittest

import ldap
import os

import splat
#from splat import plugin
from splat.ldaputils.test import slapd
from splat.ldaputils import client as ldapclient
from splat.helpers import homeutils

# Useful Constants
from splat.test import DATA_DIR

# Test Cases
class HomeUtilstestCase(unittest.TestCase):
    """ Test Splat Home Directory Library """

    def setUp(self):
        self.slapd = slapd.LDAPServer()
        self.conn = ldapclient.Connection(slapd.SLAPD_URI)
        self.entry = self.conn.search(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(uid=john)')[0]

    def tearDown(self):
        self.slapd.stop()

    def test_valid_attributes(self):
        """ Test getLDAPAttributes() for Valid Entry """
        (home, uid, gid) = homeutils.getLDAPAttributes(self.entry, '/home', 10000, 10000)
        self.assertEquals(('/home/john', 10001, 10001), (home, uid, gid))

    def test_invalid_uid(self):
        """ Test getLDAPAttributes() for Entry with UID Lower than Minimum """
        self.assertRaises(splat.SplatError, homeutils.getLDAPAttributes, self.entry, '/home', 20000, 10000)

    def test_invalid_gid(self):
        """ Test getLDAPAttributes() for Entry with GID Lower than Minimum """
        self.assertRaises(splat.SplatError, homeutils.getLDAPAttributes, self.entry, '/home', 10000, 20000)

    def test_invalid_home(self):
        """ Test getLDAPAttributes() for Entry with Invalid Home Directory """
        self.assertRaises(splat.SplatError, homeutils.getLDAPAttributes, self.entry, '/tmp', 10000, 10000)
