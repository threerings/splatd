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

import os
import logging
import shutil
import posix
import tarfile
import splat
from splat import plugin

logger = logging.getLogger(splat.LOG_NAME)

class WriterContext(object):
    """ Option Context """
    def __init__(self):
        self.archiveHomeDir = True
        self.purgeHomeDir = True
        self.purgeHomeArchive = True
        self.archiveDest = '/home'

class Writer(plugin.Helper):
    def attributes(self): 
        """
        Attributes we are interested in. Note that entries may not have 
        all of these attributes, and we only need most of them if we 
        are going to be purging or archiving.
        """
        return ('pendingPurge', 'homeDirectory', 'uidNumber', 'gidNumber')

    def parseOptions(self, options):
        context = WriterContext()
        for key in options.keys():
            if (key == 'archivehomedir'):
                context.archiveHomeDir = self._parseBooleanOption(str(options[key]))
                continue
            if (key == 'purgehomedir'):
                context.purgeHomeDir = self._parseBooleanOption(str(options[key]))
                continue
            if (key == 'purgehomearchive'):
                context.purgeHomeArchive = self._parseBooleanOption(str(options[key]))
                continue
            if (key == 'archivedest'):
                context.archiveDest = os.path.abspath(options[key])
                continue
            raise plugin.SplatPluginError, "Invalid option '%s' specified." % key
        
        # Validation of some options.
        if (context.purgeHomeArchive and not context.archiveHomeDir):
            raise plugin.SplatPluginError, "Cannot purge home directory archives if the archives are never created. Set archivehomedir to true."
        if (context.archiveHomeDir):
            if (not os.path.isdir(context.archiveDest)):
                raise plugin.SplatPluginError, "Archive destination directory %s does not exist or is not a directory" % context.archiveDest

        return context
    
    def _archiveHomeDir(self, home, destination):
        pass
        # Create new gzipped tar file in destination
        
        # Recursively add all files in homedir to tar file
        
        # Return absolute path to tarball
        
    def _purgeHomeDir(self, home, uid, gid):
        pass
        # Fork and drop privileges
        
        # Recursively remove directory
        
    def _purgeHomeArchive(self, archive):
        pass

    def work(self, context, ldapEntry, modified):
        # Do nothing for entries that have not been modified
        if (not modified):
            return
