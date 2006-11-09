#!/usr/bin/env python
# test_homeDirectory.py vi:ts=4:sw=4:expandtab:
#
# Scalable Periodic LDAP Attribute Transmogrifier
# Authors:
#       Nick Barkas <snb@threerings.net>
# Based on ssh key helper tests by:
#       Landon Fuller <landonf@threerings.net>
#       Will Barton <wbb4@opendarwin.org>
#
# Copyright (c) 2006 Three Rings Design, Inc.
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
from splat import plugin
from splat.ldaputils.test import slapd
from splat.ldaputils import client as ldapclient

# Useful Constants
from splat.test import DATA_DIR

# Test Cases
class HomeDirtestCase(unittest.TestCase):
    def _getDefaultOptions(self):
        # Ubuntu (and probably Debian and other linuxes) use /etc/skel instead
        # of /usr/share skel.
        skelDir = '/usr/share/skel'
        if (not os.path.isdir(skelDir)):
            if (os.path.isdir('/etc/skel')):
                skelDir = '/etc/skel'
            else:
                self.fail('Can not find a useable skeletal directory')
            
        return { 

            'home':'/home',
            'minuid':'0',
            'mingid':'0',
            'skeldir':skelDir
        }
        
    """ Test Splat Home Directory Helper """

    def setUp(self):
        self.slapd = slapd.LDAPServer()
        self.conn = ldapclient.Connection(slapd.SLAPD_URI)
        self.hc = plugin.HelperController('test', 'splat.helpers.homeDirectory', 5, 'dc=example,dc=com', '(uid=john)', False, self._getDefaultOptions())
        self.entries = self.conn.search(self.hc.searchBase, ldap.SCOPE_SUBTREE, self.hc.searchFilter, self.hc.searchAttr)

    def tearDown(self):
        self.slapd.stop()

    def test_option_parser(self):
        """ Test Options Parser """
        # foo is not a valid option
        options = self._getDefaultOptions()
        options['foo'] = 'bar' 
        self.assertRaises(splat.SplatError, self.hc.helper.parseOptions, options)
        # Make sure the parser works when all options are valid
        del options['foo']
        assert self.hc.helper.parseOptions(options)
        # Also make sure parser works when skeldir has not been defined
        del options['skeldir']
        assert self.hc.helper.parseOptions(options)

    def test_option_parse_home(self):
        """ Test Home Option Parser """
        # Relative paths shouldn't be allowed for home
        options = self._getDefaultOptions()
        options['home'] = 'home'
        self.assertRaises(splat.SplatError, self.hc.helper.parseOptions, options)

    def test_option_parse_skeldir(self):
        """ Test Skel Directory Option Parser """
        # Paths that don't exist should generate an exception
        options = self._getDefaultOptions()
        options['skeldir'] = '/asdf/jklh/qwer'
        self.assertRaises(splat.SplatError, self.hc.helper.parseOptions, options)

    def test_validation_home(self):
        """ Test Home Validation """
        options = self._getDefaultOptions()
        options['home'] = '/etc'
        self.context = self.hc.helper.parseOptions(options)
        self.assertRaises(splat.SplatError, self.hc.helper.getAttributes, self.context, self.entries[0])

    def test_validation_uid(self):
        """ Test UID Validation """
        options = self._getDefaultOptions()
        options['minuid'] = '9000000'
        self.context = self.hc.helper.parseOptions(options)
        self.assertRaises(splat.SplatError, self.hc.helper.getAttributes, self.context, self.entries[0])

    def test_validation_home(self):
        """ Test GID Validation """
        options = self._getDefaultOptions()
        options['mingid'] = '9000000'
        self.context = self.hc.helper.parseOptions(options)
        self.assertRaises(splat.SplatError, self.hc.helper.getAttributes, self.context, self.entries[0])

    def test_attributes(self):
        """ Test Attributes """
        options = self._getDefaultOptions()
        self.context = self.hc.helper.parseOptions(options)
        realAttrs = ('/home/john', 10001, 10001)
        attrs = self.hc.helper.getAttributes(self.context, self.entries[0])
        self.failUnlessEqual(realAttrs, attrs)

