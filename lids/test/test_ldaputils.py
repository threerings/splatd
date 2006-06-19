#!/usr/bin/env python
# test_ldap.py vi:ts=4:sw=4:expandtab:
#
# LDAP Information Distribution System
# Authors:
#       Landon Fuller <landonf@threerings.net>
#       Will Barton <wbb4@opendarwin.org>
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

""" LDAP Unit Tests """

from twisted.trial import unittest
import ldap

from lids import ldaputils

# Useful Constants
from lids.test import DATA_DIR
from lids.test import slapd

# Test Cases
class ConnectionTestCase(unittest.TestCase):
    """ Test LDAP Connection """
    def setUp(self):
        self.slapd = slapd.LDAPServer()
        self.conn = ldaputils.Connection(slapd.SLAPD_URI)

    def tearDown(self):
        self.slapd.stop()

    def test_initialize(self):
        self.assertEquals(self.conn._ldap.protocol_version, ldap.VERSION3)

    def test_simple_bind(self):
        self.conn.simple_bind(slapd.ROOTDN, slapd.ROOTPW)

    def test_gssapi_bind(self):
        # If SASL support isn't available, skip the test.
        if (not ldap.SASL_AVAIL):
            raise unittest.SkipTest('LDAP SASL support unavailable, nothing to test')

        # I am not crazy enough to try and automatically
        # set up a local kerberos server to test this ...
        # Force it to fail, validate the failure.
        self.assertRaises(ldap.LOCAL_ERROR, self.conn.gssapi_bind,'big/failure@EXAMPLE.COM')

    def test_search(self):
        result = self.conn.search(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(uid=john)', ['uid',])
        self.assertEquals(result[0].attributes['uid'][0], 'john')

    def test_modify(self):
        # Acquire write privs
        self.conn.simple_bind(slapd.ROOTDN, slapd.ROOTPW)

        # Find entry
        entry = self.conn.search(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(uid=john)', None)[0]
        mod = ldaputils.Modification(entry.dn)

        # Test MOD_REPLACE with multiple values ...
        mod.replace('description', ['Test1', 'Test2'])

        # Test MOD_ADD
        mod.add('street', 'Test')
        # ... with multiple values
        mod.add('mail', ['test1@example.com', 'test2@example.com'])

        # Test MOD_DELETE
        mod.delete('loginShell')
        # ... with a value specified
        mod.delete('mail', 'johnalias@example.com')

        # Do modification
        self.conn.modify(mod)

        # Verify the result
        entry = self.conn.search(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(uid=john)', ['description', 'street', 'mail'])[0]
        # We replaced all values of 'description'
        self.assertEquals(len(entry.attributes.get('description')), 2)
        self.assertEquals(entry.attributes.get('description')[0], 'Test1')
        self.assertEquals(entry.attributes.get('description')[1], 'Test2')

        # Added the street
        self.assertEquals(entry.attributes.get('street')[0], 'Test')

        # There should be three values
        self.assertEquals(len(entry.attributes.get('mail')), 3)
        self.assertEquals(entry.attributes.get('mail')[0], 'john@example.com')
        self.assertEquals(entry.attributes.get('mail')[1], 'test1@example.com')
        self.assertEquals(entry.attributes.get('mail')[2], 'test2@example.com')

        # loginShell was deleted
        self.assert_(not entry.attributes.has_key('loginShell'))


class EntryTestCase(unittest.TestCase):
    """ Test LDAP Entry Objects """
    def setUp(self):
        self.slapd = slapd.LDAPServer()
        self.conn = ldaputils.Connection(slapd.SLAPD_URI)

    def tearDown(self):
        self.slapd.stop()

    def test_search_result(self):
        result = self.conn.search(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(uid=john)', ['uid',])
        self.assertEquals(result[0].attributes['uid'][0], 'john')
        self.assertEquals(result[0].dn, 'uid=john,ou=People,dc=example,dc=com')


class ModificationTestCase(unittest.TestCase):
    """ Test LDAP Modification Objects """
    def setUp(self):
        self.slapd = slapd.LDAPServer()
        self.conn = ldaputils.Connection(slapd.SLAPD_URI)
        entry = self.conn.search(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(uid=john)')[0]
        self.mod = ldaputils.Modification(entry.dn)

    def tearDown(self):
        self.slapd.stop()

    def test_add(self):
        self.mod.add('uid', 'test')
        self.assertEquals(self.mod.modlist, [(ldap.MOD_ADD, 'uid', 'test'),])
        self.mod.add('uid', ['test1', 'test2'])
        self.assertEquals(self.mod.modlist, [
                (ldap.MOD_ADD, 'uid', 'test'),
                (ldap.MOD_ADD, 'uid', ['test1', 'test2'])
        ])

    def test_replace(self):
        self.mod.replace('uid', 'test')
        self.assertEquals(self.mod.modlist, [(ldap.MOD_REPLACE, 'uid', 'test'),])
        self.mod.replace('uid', ['test1', 'test2'])
        self.assertEquals(self.mod.modlist, [
                (ldap.MOD_REPLACE, 'uid', 'test'),
                (ldap.MOD_REPLACE, 'uid', ['test1', 'test2'])
        ])

    def test_delete(self):
        self.mod.delete('cn')
        self.assertEquals(self.mod.modlist, [(ldap.MOD_DELETE, 'cn', None),])

        self.mod.delete('cn', ['John Doe', 'John Doe II'])
        self.assertEquals(self.mod.modlist, [
                (ldap.MOD_DELETE, 'cn', None),
                (ldap.MOD_DELETE, 'cn', ['John Doe', 'John Doe II'])
        ])


class GroupFilterTestCase(unittest.TestCase):
    """ Test Group Filters """
    def setUp(self):
        self.slapd = slapd.LDAPServer()
        self.conn = ldaputils.Connection(slapd.SLAPD_URI)
        self.entry = self.conn.search(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(uid=john)')[0]

    def tearDown(self):
        self.slapd.stop()

    def test_isMember(self):
        # Matching member
        filter = ldaputils.GroupFilter(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(&(objectClass=groupOfUniqueNames)(cn=developers))')
        self.assert_(filter.isMember(self.conn, self.entry.dn))

        # Should not match
        filter = ldaputils.GroupFilter(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(&(objectClass=groupOfUniqueNames)(cn=administrators))')
        self.assert_(not filter.isMember(self.conn, self.entry.dn))

        # Try with a custom matching attribute
        filter = ldaputils.GroupFilter(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(&(objectClass=groupOfNames)(cn=notunique))', 'member')
        self.assert_(filter.isMember(self.conn, self.entry.dn))

    def test_caching(self):
        filter = ldaputils.GroupFilter(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(&(objectClass=groupOfUniqueNames)(cn=developers))', 'uniqueMember')

        # Set a silly cache TTL to ensure it will never expire
        filter.cacheTTL = 3000000
        self.assert_(filter.isMember(self.conn, self.entry.dn))

        # Acquire write privs
        self.conn.simple_bind(slapd.ROOTDN, slapd.ROOTPW)

        # Drop self.entry.dn from the developers group
        group = self.conn.search(slapd.BASEDN, ldap.SCOPE_SUBTREE, '(&(objectClass=groupOfUniqueNames)(cn=developers))')[0]
        mod = ldaputils.Modification(group.dn)
        mod.delete('uniqueMember', self.entry.dn)
        self.conn.modify(mod)

        # Verify that the group filter is still using the cached results
        self.assert_(filter.isMember(self.conn, self.entry.dn))

        # Drop the cache TTL to force the filter to update its cache and
        # then verify that the cache has been updated
        filter.cacheTTL = 0
        self.assert_(not filter.isMember(self.conn, self.entry.dn))
