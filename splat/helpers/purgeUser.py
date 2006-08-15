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

# Child process exit codes
PURGE_ERR_NONE = 0
PURGE_ERR_PRIVSEP = 1
PURGE_ERR_CHDIR = 2
PURGE_ERR_DELTREE = 3

class WriterContext(object):
    """ Option Context """
    def __init__(self):
        self.archiveHomeDir = True
        self.purgeHomeDir = True
        self.purgeHomeArchive = True
        self.archiveDest = '/home'
        self.purgeArchiveWait = 14

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
            if (key == 'purgearchivewait'):
                context.purgeArchiveWait = int(options[key])
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
    
    # Drops privileges to the owner of home directory, then recursive removes 
    # all files in it. If this succeeds, the (probably empty) home directory
    # will be removed by the privileged user splatd runs as.
    def _purgeHomeDir(self, home, uid, gid):
        # File descriptors to use for error strings from child process
        pipe = os.pipe()
        infd = os.fdopen(pipe[0], 'r')
        outfd = os.fdopen(pipe[1], 'w')
        
        # Fork and drop privileges
        pid = os.fork()
        
        if (pid == 0):
            try:
                os.setgid(gid)
                os.setuid(uid)
            except OSError, e:
                outfd.write(str(e))
                outfd.close()
                os._exit(PURGE_ERR_PRIVSEP)
        
            # Recursively remove directory
            try:
                os.chdir(home)
            except OSError, e:
                outfd.write(str(e))
                outfd.close()
                os._exit(PURGE_ERR_CHDIR)
            try:
                for filename in os.listdir(home):
                    shutil.deltree(filename)
            except OSError, e:
                outfd.write(str(e))
                outfd.close()
                os._exit(PURGE_ERR_DELTREE)
            
            sys._exit(PURGE_ERR_NONE)
            
        # Wait for child to exit
        while True:
            try:
                result = os.waitpid(pid, 0)
            except OSError, e:
                if (e.errno == errno.EINTR):
                    continue
                raise
            break

        # Check exit status of child process
        status = os.WEXITSTATUS(result[1])
        if (status == PURGE_ERR_NONE):
            outfd.close()
            infd.close()
            # If everything went ok, delete home directory
            try:
                os.rmdir(home)
            except OSError, e:
                raise plugin.SplatPluginError, "Unable to remove directory %s: %s" % (home, str(e))
            logger.info("Home directory %s purged successfully." % home)
            
        # Deal with error conditions
        else:
            error = infd.readline()
            infd.close()
            if (status == PURGE_ERR_PRIVSEP):
                raise plugin.SplatPluginError, "Unable to drop privileges to uid %d, gid %d and purge %s: %s" % (uid, gid, home, error)
            elif (status == PURGE_ERR_CHDIR):
                raise plugin.SplatPluginError, "Unable to change directory to %s: %s" % (home, error)
            elif (status == PURGE_ERR_DELTREE):
                raise plugin.SplatPluginError, "Unable to remove all files in %s: %s" % (home, error)
        
    def _purgeHomeArchive(self, archive):
        pass

    def work(self, context, ldapEntry, modified):
        pass            
        # if archiveHomeDir and not already archived, archive homedir
        
        # if purgeHomeDir, not already purged, and past pendingPurge, purge homedir
        
        # if purgeArchiveWait days past purge date and purgeHomeArchive, rm it
