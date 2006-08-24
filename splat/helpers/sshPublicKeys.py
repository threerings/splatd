# sshPublicKeys.py vi:ts=4:sw=4:expandtab:
#
# LDAP SSH Public Key Helper.
# Authors:
#       Will Barton <wbb4@opendarwin.org>
#       Landon Fuller <landonf@threerings.net>
#
# Copyright (c) 2005, 2006 Three Rings Design, Inc.
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

import sys, logging, errno, string
import os, stat, time

import splat
from splat import plugin

import homeDirectory

logger = logging.getLogger(splat.LOG_NAME)

# Sub-process result codes
SSH_ERR_NONE = 0
SSH_ERR_MISC = 1
SSH_ERR_PRIVSEP = 2
SSH_ERR_WRITE = 3
class WriterContext(homeDirectory.WriterContext):
    def __init__(self):
        homeDirectory.WriterContext.__init__(self)
        self.command = None
        self.makehome = False

class Writer(homeDirectory.Writer):
    # Required Attributes
    def attributes(self): 
        return ('sshPublicKey',) + homeDirectory.Writer.attributes(self) 

    def parseOptions(self, options):
        context = WriterContext()

        # Get command and makehome options, if they were given
        for key in options.keys():
            if (key == 'command'):
                context.command = options[key]
                # Superclass parseOptions() method won't like this option
                del options[key]
                continue
            if (key == 'makehome'):
                context.makehome = self._parseBooleanOption(str(options[key]))
                del options[key]
                continue
                
        # Add options superclass is concerned with to context.
        superContext = vars(homeDirectory.Writer.parseOptions(self, options))
        for opt in superContext.keys():
            setattr(context, opt, superContext[opt])
        
        return context

    def work(self, context, ldapEntry, modified):
        # Skip unmodified entries
        if (not modified):
            return

        # Get all needed LDAP attributes, and verify we have what we need
        attributes = ldapEntry.attributes
        if (not attributes.has_key('sshPublicKey')):
            raise plugin.SplatPluginError, "Required attribute sshPublicKey not specified."
        keys = attributes.get("sshPublicKey")
        (home, uid, gid) = self.getAttributes(context, ldapEntry)

        # Make sure the home directory exists, and make it if config says to
        if (not os.path.isdir(home)):
            if (context.makehome == True):
                homeDirectory.Writer.work(self, context, ldapEntry, modified)
            else:
                # If we weren't told to make homedir, log a warning and quit
                logger.warning("SSH keys not being written because home directory %s does not exist. To have this home directory created automatically by this plugin, set the makehome option to true in your splat configuration file, or use the homeDirectory plugin." % home)
                return


        sshdir = "%s/.ssh" % home
        tmpfilename = "%s/.ssh/authorized_keys.tmp" % home
        filename = "%s/.ssh/authorized_keys" % home

        # Make sure the modifyTimestamp entry exists before looking at it
        if (ldapEntry.attributes.has_key('modifyTimestamp')):
    
            # stat() the key, check if it is outdated
            try:
                keyTime = os.stat(filename)[stat.ST_MTIME]
                # Convert LDAP UTC time to seconds since epoch
                entryTime = time.mktime(time.strptime(ldapEntry.attributes['modifyTimestamp'][0] + 'UTC', "%Y%m%d%H%M%SZ%Z")) - time.timezone
    
                # If the entry is older than the key, skip it.
                # This will only occur on the very first daemon iteration,
                # where modified is always 'True'
                if (entryTime < keyTime):
                    logger.info("Skipping %s, up-to-date" % filename)
                    return
    
            except OSError:
                # File doesn't exist, or some other error.
                # Ignore the exception, it'll be caught again
                # and reported below.
                pass

        logger.info("Writing key to %s" % filename)

        # Fork and setuid to write the files
        pipe = os.pipe()
        outf = os.fdopen(pipe[1], 'w')
        inf = os.fdopen(pipe[0], 'r')

        pid = os.fork()
        if (pid == 0):
            # Drop privs
            try:
                os.setgid(gid)
                os.setuid(uid)
            except OSError, e:
                print str(e)
                outf.write(str(e) + '\n')
                outf.close()
                os._exit(SSH_ERR_PRIVSEP)

            # Adopt a strict umask
            os.umask(077)

            # Create .ssh directory if it does not already exist
            if (not os.path.isdir(sshdir)):
                try:
                    os.mkdir(sshdir)
                except OSError, e:
                    outf.write(str(e) + '\n')
                    outf.close()
                    os._exit(SSH_ERR_WRITE)

            try:
                f = open(tmpfilename, "w+")
                for key in keys:
                    if (context.command == None):
                        contents = "%s\n" % key
                    else:
                        contents = "command=\"%s\" %s\n" % (context.command, key)

                    f.write(contents)
                f.close()
            except IOError, e:
                outf.write(str(e) + '\n')
                outf.close()
                os._exit(SSH_ERR_WRITE)

            # Move key to ~/.ssh/authorized_keys
            try:
                os.rename(tmpfilename, filename)
            except OSError, e:
                outf.write(str(e) + '\n')
                outf.close()
                os._exit(SSH_ERR_WRITE)

            os._exit(SSH_ERR_NONE)
        else:
            while (1):
                try:
                    result = os.waitpid(pid, 0)
                except OSError, e:
                    if (e.errno == errno.EINTR):
                        continue
                    raise
                break

            status = os.WEXITSTATUS(result[1])

        # Handle the error conditions
        if (status == SSH_ERR_NONE):
            outf.close()
            inf.close()
            return
        else:
            errstr = inf.readline()
            outf.close()
            inf.close()

        if (status == SSH_ERR_PRIVSEP):
            raise plugin.SplatPluginError, "Failed to drop privileges, %s" % errstr

        if (status == SSH_ERR_WRITE):
            raise plugin.SplatPluginError, "Failed to write SSH key, %s" % errstr
