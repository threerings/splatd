# purgeUser.py vi:ts=4:sw=4:expandtab:
#
# LDAP User Purging Helper.
# Author:
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

import os, logging, shutil

import splat
from splat import plugin

logger = logging.getLogger(splat.LOG_NAME)

class WriterContext(object):
    """ Option Context """
    def __init__(self):
        self.archivehomedir = True
        self.purgehomedir = True
        self.purgehomearchive = True
        self.archivedest = '/home'

class Writer(plugin.Helper):
    # Attributes we are interested in. Note that entries may not have all of 
    # these attributes, and we only need most of them if we are going to be 
    # purging or archiving. 
    def attributes(self): 
        return ('accountStatus', 'pendingPurge', 'homeDirectory', 'uidNumber', 'gidNumber')

    # Helper method to case insensitively convert a string option 'true' or 
    # 'false' to the appropriate boolean, and throw an exception if the option 
    # isn't either of those strings.
    def _parseBooleanOption(self, option):
        if (string.lower(option) == 'true'):
            return True
        elif (string.lower(option) == 'false'):
            return False
        else:
            raise plugin.SplatPluginError, "Invalid value for option %s specified; must be set to true or false." % option

    def parseOptions(self, options):
        context = WriterContext()
        for key in options.keys():
            if (key == 'archivehomedir'):
                context.archivehomedir = self._parseBooleanOption(str(options[key]))
                continue
            if (key == 'purgehomedir'):
                context.purgehomedir = self._parseBooleanOption(str(options[key]))
                continue
            if (key == 'purgehomearchive'):
                context.purgehomearchive = self._parseBooleanOption(str(options[key]))
                continue
            if (key == 'archivedest'):
                context.archivedest = os.path.abspath(options[key])
                continue
            raise plugin.SplatPluginError, "Invalid option '%s' specified." % key
        
        # Validation of some options.
        if (context.purgehomearchive and not context.archivehomedir):
            raise plugin.SplatPluginError, "Cannot purge home directory archives if the archives are never created. Set archivehomedir to true."
        if (context.archivehomedir):
            if (not os.path.isdir(context.archivedest)):
                raise plugin.SplatPluginError, "Archive destination directory %s does not exist or is not a directory" % context.archivedest

        return context
            
    def _archiveHomeDir(self, home, destination):
        # Adopt a strict umask
        os.umask(077)
        
        # Create new gzipped tar file in destination
        
        # Recursively add all files in homedir to tar file
        
        # Return absolute path to tarball
        
    def _purgeHomeDir(self, home, uid, gid):
        # Fork and drop privileges
        
        # Recursively remove directory
        
    def _purgeHomeArchive(self, archive):

    def work(self, context, ldapEntry, modified):
        # Do nothing for entries that have not been modified
        if (not modified):
            return
        
        # Get attributes from LDAP entry and make sure we have at least 
        # accountStatus.
        attributes = ldapEntry.attributes
        if (not attributes.has_key('accountStatus')):
            raise plugin.SplatPluginError, "Required attribute accountStatus not specified."
        
        # If the account is active, nothing to do
        if (attributes.get('accountStatus') == 'active'):
            return
            
