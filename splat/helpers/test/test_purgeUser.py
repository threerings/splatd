#!/usr/bin/env python
# test_purgeUser.py vi:ts=4:sw=4:expandtab:
#
# Scalable Periodic LDAP Attribute Transmogrifier
# Authors:
#       Nick Barkas <snb@threerings.net>
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

import ldap
import splat
import time
from twisted.trial import unittest
from splat import plugin
from splat.ldaputils import client as ldapclient
from splat.ldaputils.test import slapd

# Useful Constants
from splat.test import DATA_DIR

class PurgeUserTestCase(unittest.TestCase):
    """ Test Splat User Purging Helper """
    
    def _setPendingPurge(self, dn):
        # Timestamp for this time yesterday in GMT, formatted for LDAP. 
        yesterday = time.strftime('%Y%m%d%H%M%SZ', time.gmtime(time.time() - 86400))
        self.conn.simple_bind('cn=Manager,dc=example,dc=com', 'secret')
        # Add a pendingPurge time in the past for the account specified by dn
        mod = ldapclient.Modification(dn)
        mod.add('pendingPurge', yesterday)
        self.conn.modify(mod)
        return yesterday
    
    # Return a valid options dictionary to parse. Note that these options are 
    # not necessarily the same as the defaults specified in the various plugin 
    # WriterContext classes.
    def _getDefaultOptions(self):
        return {
            'archivehomedir':'false',
            'purgehomedir':'false',
            'purgehomearchive':'false',
            'archivedest':'/tmp',
            'purgearchivewait':'5'
        }
    
    def setUp(self):
        self.slapd = slapd.LDAPServer()
        self.conn = ldapclient.Connection(slapd.SLAPD_URI)
        
        self.hc = plugin.HelperController('test', 'splat.helpers.purgeUser', 5, 'dc=example,dc=com', '(objectClass=purgeableAccount)', False, self._getDefaultOptions())
        self.entries = self.conn.search(self.hc.searchBase, ldap.SCOPE_SUBTREE, self.hc.searchFilter, self.hc.searchAttr)
        # We test that checking the modification timestamp on entries works in
        # plugin.py's test class, so just assume the entry is modified here.
        self.modified = True

    def tearDown(self):
        self.slapd.stop()

    def test_pendingPurge(self):
        """ Test pendingPurge Attribute """
        yesterday = self._setPendingPurge('uid=chris,ou=People,dc=example,dc=com')
        results = self.conn.search('dc=example,dc=com', ldap.SCOPE_SUBTREE, '(uid=chris)', None)
        self.assertEqual(yesterday, results[0].attributes['pendingPurge'][0])

    def test_invalid_options(self):
        """ Test Invalid Options """
        options = self._getDefaultOptions()
        options['foo'] = 'bar'
        # First test if the parser complains about invalid options.
        self.assertRaises(splat.SplatError, self.hc.helperClass.parseOptions, options)
        # Then make sure it works when the options are valid.
        del options['foo']
        assert self.hc.helperClass.parseOptions(options)

    def test_default_options(self):
        """ Test Default Options """
        context = self.hc.helperClass.parseOptions({})
        self.assertEqual(True, context.archiveHomeDir)
        self.assertEqual(True, context.purgeHomeDir)
        self.assertEqual(True, context.purgeHomeArchive)
        self.assertEqual('/home', context.archiveDest)
        self.assertEqual(14, context.purgeArchiveWait)
        
    def test_bad_option_values(self):
        """ Test Validation of Bad Option Values """
        self.assertRaises(splat.SplatError, self.hc.helperClass.parseOptions, {'archivedest':'/asdf'})
        self.assertRaises(splat.SplatError, self.hc.helperClass.parseOptions, {'purgehomedir':'42'})
        self.assertRaises(splat.SplatError, self.hc.helperClass.parseOptions, {'archivehomedir':'false', 'purgehomearchive':'true'})

    def test_context(self):
        """ Test Context Consistency With Options """
        context = self.hc.helperClass.parseOptions(self._getDefaultOptions())
        self.assertEqual(False, context.archiveHomeDir)
        self.assertEqual(False, context.purgeHomeDir)
        self.assertEqual(False, context.purgeHomeArchive)
        self.assertEqual('/tmp', context.archiveDest)
        self.assertEqual(5, context.purgeArchiveWait)
