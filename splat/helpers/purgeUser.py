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
import tarfile
import time
import errno
import homeHelper
import splat
from splat import plugin

logger = logging.getLogger(splat.LOG_NAME)

# Child process exit codes
PURGE_ERR_NONE = 0
PURGE_ERR_PRIVSEP = 1
PURGE_ERR_RM = 2

class WriterContext(homeHelper.WriterContext):
    def __init__(self):
        homeHelper.WriterContext.__init__(self)
        self.archiveHomeDir = True
        self.purgeHomeDir = True
        self.purgeHomeArchive = True
        self.archiveDest = '/home'
        self.purgeArchiveWait = 14

class Writer(homeHelper.Writer):
    def attributes(self): 
        return ('pendingPurge', 'uid') + homeHelper.Writer.attributes(self)

    def parseOptions(self, options):
        context = WriterContext()
        # Add options superclass is concerned with to context.
        superContext = vars(homeHelper.Writer.parseOptions(self, options))
        for opt in superContext.keys():
            setattr(context, opt, superContext[opt])
                
        for key in options.iterkeys():
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
            if (context.archiveDest[0] != '/'):
                raise plugin.SplatPluginError, "Relative paths for the archivedest option are not permitted."
            if (not os.path.isdir(context.archiveDest)):
                raise plugin.SplatPluginError, "Archive destination directory %s does not exist or is not a directory" % context.archiveDest

        return context
    
    # Creates a tarred and gzipped archive of a home directory. 
    def _archiveHomeDir(self, home, archiveFile):
        # Create new gzipped tar file. Have to use os.open() to create it, 
        # close, then use tarfile.open() because tarfile.open() does not let 
        # you set file permissions.
        try:
            fd = os.open(archiveFile, os.O_CREAT, 0600)
            os.close(fd)
            archive = tarfile.open(archiveFile, 'w:gz')
        except (IOError, OSError), e:
            raise plugin.SplatPluginError, "Cannot create archive file %s: %s" % (archiveFile, str(e))
        
        # Strip any trailing / characters from home
        home = os.path.normpath(home)
        
        # Add all files in homedir to tar file
        try:
            archive.add(home, arcname=os.path.basename(home))
            # Keep close in the try block too, because it will throw an 
            # exception if we run out of space.
            archive.close()
            logger.info("Archive %s created." % archiveFile)
        except (IOError, OSError), e:
            raise plugin.SplatPluginError, "Unable to add all files to archive %s: %s" % (archiveFile, e)
            
    # Drops privileges to the owner of home directory, then recursive removes 
    # all files in it. If this succeeds, the (probably empty) home directory
    # will be removed by the privileged user splatd runs as.
    def _purgeHomeDir(self, home, uidNumber, gidNumber):
        # File descriptors to use for error strings from child process
        pipe = os.pipe()
        infd = os.fdopen(pipe[0], 'r')
        outfd = os.fdopen(pipe[1], 'w')
        
        # Fork and drop privileges
        pid = os.fork()
        
        if (pid == 0):
            try:
                os.setgid(gidNumber)
                os.setuid(uidNumber)
            except OSError, e:
                outfd.write(str(e) + '\n')
                outfd.close()
                os._exit(PURGE_ERR_PRIVSEP)
        
            # Recursively remove home directory contents
            try:
                for filename in os.listdir(home):
                    absPath = os.path.join(home, filename)
                    if (os.path.isdir(absPath)):
                        shutil.rmtree(absPath)
                    else:
                        os.remove(absPath)
            except OSError, e:
                outfd.write(str(e) + '\n')
                outfd.close()
                os._exit(PURGE_ERR_RM)

            os._exit(PURGE_ERR_NONE)
            
        # Wait for child to exit
        else:
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
                raise plugin.SplatPluginError, "Unable to drop privileges to uid number %d, gid number %d and purge %s: %s" % (uidNumber, gidNumber, home, error)
            elif (status == PURGE_ERR_RM):
                raise plugin.SplatPluginError, "Unable to remove all files in %s: %s" % (home, error)
        
    # Unlink the specified file archive, which should be an archived homedir.
    def _purgeHomeArchive(self, archive):
        try:
            os.remove(archive)
        except OSError, e:
            raise plugin.SplatPluginError, "Unable to remove archive %s: %s" % (archive, str(e))
        logger.info("Archive %s removed successfully." % archive)

    def work(self, context, ldapEntry, modified):
        # Get all needed LDAP attributes, and verify we have what we need
        attributes = ldapEntry.attributes
        if (not attributes.has_key('pendingPurge')):
            raise plugin.SplatPluginError, "Required attribute pendingPurge not found in LDAP entry."
        if (not attributes.has_key('uid')):
            raise plugin.SplatPluginError, "Required attribute uid not found in LDAP entry."
        pendingPurge = attributes.get('pendingPurge')[0]
        username = attributes.get('uid')[0]
        (home, uidNumber, gidNumber) = self.getAttributes(context, ldapEntry)
        
        # Get current time (in GMT). 
        now = int(time.strftime('%Y%m%d%H%M%S', time.gmtime(time.time())))
        
        # Do nothing if pendingPurge is still in the future. 
        if (now < int(pendingPurge.rstrip('Z'))):
            return
        
        # If archiveHomeDir and not already archived or purged, archive homedir.
        archiveFile = os.path.join(context.archiveDest, os.path.basename(home) + '.tar.gz')
        if (context.archiveHomeDir and (not os.path.isfile(archiveFile)) and os.path.isdir(home)):
            self._archiveHomeDir(home, archiveFile)
        
        # If purgeHomeDir and not already purged, purge homedir.
        if (context.purgeHomeDir and os.path.isdir(home)):
            self._purgeHomeDir(home, uidNumber, gidNumber)
        
        # Purge archive if it is old enough, and we are supposed to purge them.
        if (context.purgeHomeArchive and os.path.isfile(archiveFile)):
            # Number of seconds since archiveFile was last modified.
            archiveModifiedAge = int(time.time()) - os.path.getmtime(archiveFile)
            if ((archiveModifiedAge / 86400) > context.purgeArchiveWait):
                self._purgeHomeArchive(archiveFile)
