#!/usr/bin/env python
# slapd.py vi:ts=4:sw=4:expandtab:
#
# Scalable Periodic LDAP Attribute Transmogrifier
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

"""
LDAP Server Test Harness
Initializes the directory with test data and invokes slapd listening on a unix domain socket
"""

import os, posix, shutil, signal
import subprocess, urllib

# Useful Constants
from splat.test import DATA_DIR
LDAP_DIR = os.path.join(DATA_DIR, 'openldap')

SLAPD_CONFIG = os.path.join(LDAP_DIR, 'slapd.conf')
SLAPD_CONFIG_IN = os.path.join(LDAP_DIR, 'slapd.conf.in')
SLAPD_SOCKET = os.path.join(LDAP_DIR, 'slapi')
SLAPD_URI = 'ldapi://' + os.path.join(urllib.quote(LDAP_DIR), 'slapi').replace('/', '%2F')
SLAPD_DATA = os.path.join(LDAP_DIR, 'openldap-data')
SLAPD_LDIF = os.path.join(LDAP_DIR, 'test.ldif')

SLAPD_PATHS = [
    '/usr/local/libexec/slapd',
    '/opt/local/libexec/slapd',
    '/usr/sbin/slapd',
    None
]

ROOTDN = 'cn=Manager,dc=example,dc=com'
ROOTPW = 'secret'
BASEDN = 'dc=example,dc=com'

class LDAPServer(object):
    def __init__(self):
        # Find the slapd binary
        for slapd in SLAPD_PATHS:
            if (os.path.isfile(slapd)):
                break
        assert(slapd != None)

        self._clean()

        # Fix up paths in the slapd configuration file
        output = open(SLAPD_CONFIG, 'w')
        input = open(SLAPD_CONFIG_IN, 'r')
        for line in input:
            line = line.replace('@LDAP_DIR@', LDAP_DIR)
            output.write(line)

        output.close()
        input.close()

        # Load the directory with our test data
        posix.mkdir(SLAPD_DATA)
        pid = os.spawnv(os.P_NOWAIT, slapd, [slapd, '-T', 'a', '-f', SLAPD_CONFIG, '-l', SLAPD_LDIF])
        # Wait for completion
        while(1):
            try:
                os.waitpid(pid, 0)
            except OSError, e:
                import errno
                if e.errno == errno.EINTR:
                    continue
                raise
            break

        # Fire up the LDAP server
        self._p = subprocess.Popen([slapd, '-d', '1', '-h', SLAPD_URI, '-f', SLAPD_CONFIG], stderr = subprocess.PIPE)
        # Wait for process to initialize
        while 1:
            line = self._p.stderr.readline()
            if (line == ""):
                break
            if (line == "slapd starting\n"):
                # XXX There is still a tiny race here, and there's nothing we can do about it.
                import time
                time.sleep(.01)
                break

        # We're no longer interested in stderr
        self._p.stderr = None

    def _clean(self):
        # Reset the directory data
        if (os.path.isdir(SLAPD_DATA)):
            shutil.rmtree(SLAPD_DATA)

        if (os.path.exists(SLAPD_CONFIG)):
            posix.unlink(SLAPD_CONFIG)

        if (os.path.exists(SLAPD_SOCKET)):
            posix.unlink(SLAPD_SOCKET)

    def stop(self):
        os.kill(self._p.pid, 2)
        # Wait for completion
        while(1):
            try:
                os.waitpid(self._p.pid, 0)
            except OSError, e:
                import errno
                if e.errno == errno.EINTR:
                    continue
                raise
            break
        self._clean()
