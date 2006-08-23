# homeHelper.py vi:ts=4:sw=4:expandtab:
#
# Generic helper class for plugins that deal with home directories.
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

import os
import splat
from splat import plugin

class WriterContext(object):
    """ Option Context """
    def __init__(self):
        self.minuid = None
        self.mingid = None
        self.home = None
        self.splitHome = None

class Writer(plugin.Helper):
    # Required Attributes
    def attributes(self): 
        return ('homeDirectory', 'gidNumber', 'uidNumber')

    def parseOptions(self, options):
        context = WriterContext()

        for key in options.keys():
            if (key == 'home'):
                context.home = str(options[key])
                if (context.home[0] != '/'):
                    raise plugin.SplatPluginError, "Relative paths for the home option are not permitted"
                splitHome = context.home.split('/')
                context.splitHome = splitHome
                continue
            if (key == 'minuid'):
                context.minuid = int(options[key])
                continue
            if (key == 'mingid'):
                context.mingid = int(options[key])
                continue
            raise plugin.SplatPluginError, "Invalid option '%s' specified." % key
            
        return context
        
    def getAttributes(self, context, ldapEntry):
        attributes = ldapEntry.attributes

        # Test for required attributes
        if (not (attributes.has_key('homeDirectory') and attributes.has_key('uidNumber') and attributes.has_key('gidNumber'))):
            raise plugin.SplatPluginError, "Required attributes homeDirectory, uidNumber, and gidNumber not all specified."

        home = attributes.get("homeDirectory")[0]
        uid = int(attributes.get("uidNumber")[0])
        gid = int(attributes.get("gidNumber")[0])

        # Validate the home directory
        if (context.home != None):
            givenPath = os.path.abspath(home).split('/')
            if (len(givenPath) < len(context.splitHome)):
                raise plugin.SplatPluginError, "LDAP Server returned home directory (%s) located outside of %s for entry '%s'" % (home, context.home, ldapEntry.dn)

            for i in range(0, len(context.splitHome)):
                if (context.splitHome[i] != givenPath[i]):
                    raise plugin.SplatPluginError, "LDAP Server returned home directory (%s) located outside of %s for entry '%s'" % (home, context.home, ldapEntry.dn)

        # Validate the UID
        if (context.minuid != None):
            if (context.minuid > uid):
                raise plugin.SplatPluginError, "LDAP Server returned uid %d less than specified minimum uid of %d for entry '%s'" % (uid, context.minuid, ldapEntry.dn)

        # Validate the GID
        if (context.mingid != None):
            if (context.mingid > gid):
                raise plugin.SplatPluginError, "LDAP Server returned gid %d less than specified minimum gid of %d for entry '%s'" % (gid, context.mingid, ldapEntry.dn)

        return (home, uid, gid)
