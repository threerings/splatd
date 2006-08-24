# homeDirectory.py vi:ts=4:sw=4:expandtab:
#
# LDAP Home Directory Creating Helper.
# Authors:
#       Nick Barkas <snb@threerings.net>
# Based on ssh key helper by:
#       Will Barton <wbb4@opendarwin.org>
#       Landon Fuller <landonf@threerings.net>
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

import os, logging, re, shutil, errno

import splat
from splat import plugin

import homeHelper

logger = logging.getLogger(splat.LOG_NAME)

class WriterContext(homeHelper.WriterContext):
    def __init__(self):
        homeHelper.WriterContext.__init__(self)
        self.skeldir = '/usr/share/skel' # Default skeletal home directory
        self.postcreate = None

class Writer(homeHelper.Writer):
    def parseOptions(self, options):
        context = WriterContext()
        # Get basic options using superclass parseOptions method, and copy them
        # to this context object.
        superContext = vars(homeHelper.Writer.parseOptions(self, options))
        for opt in superContext.keys():
            setattr(context, opt, superContext[opt])
        
        for key in options.keys():
            if (key == 'skeldir'):
                context.skeldir = os.path.abspath(options[key])
                # Validate skel directory
                if (not os.path.isdir(context.skeldir)):
                    raise plugin.SplatPluginError, "Skeletal home directory %s does not exist or is not a directory" % context.skeldir
                continue
            if (key == 'postcreate'):
                context.postcreate = os.path.abspath(options[key])
                continue
            raise plugin.SplatPluginError, "Invalid option '%s' specified." % key
            
        return context

    # Recursively copy a directory tree, preserving permission modes and access
    # times, but changing ownership of files to uid:gid. Also, renames
    # files/directories named dot.foo to .foo.
    def _copySkelDir(self, srcDir, destDir, uid, gid):
        # Regular expression matching files named dot.foo
        pattern = re.compile('^dot\.')
        for srcFile in os.listdir(srcDir):
            destFile = pattern.sub('.', srcFile)
            # Not portable: hardcoded / as path delimeter
            srcPath = srcDir + '/' + srcFile
            destPath = destDir + '/' + destFile

            # Go deeper if we are copying a sub directory
            if (os.path.isdir(srcPath)):
                try:
                    os.makedirs(destPath)
                    shutil.copystat(srcPath, destPath)
                except OSError, e:
                    raise plugin.SplatPluginError, "Failed to create destination directory: %s" % destPath
                    continue
                
                self._copySkelDir(srcPath, destPath, uid, gid)
            
            # Copy regular files
            else:
                try:
                    shutil.copy2(srcPath, destPath)
                except IOError, e: 
                    raise plugin.SplatPluginError, "Failed to copy %s to %s: %s" % (srcPath, destPath, e)
                    continue

            # Change ownership of files/directories after copied
            try:
                os.chown(destPath, uid, gid)
            except OSError, e:
                raise plugin.SplatPluginError, "Failed to change ownership of %s to %d:%d" % (destPath, uid, gid)
                continue

    def work(self, context, ldapEntry, modified):
        (home, uid, gid) = self.getAttributes(context, ldapEntry)

        # Create the home directory, unless it already exists
        if (not os.path.isdir(home)):
            try:
                os.makedirs(home)
                os.chown(home, uid, gid)
            except OSError, e:
                raise plugin.SplatPluginError, "Failed to create home directory, %s" % e
        # If it does already exist, do nothing at all and we are done
        else:
            return

        # Copy files from skeletal directories to user's home directory
        self._copySkelDir(context.skeldir, home, uid, gid)

        # Fork and run post create script if it was defined
        if (context.postcreate != None):
            pipe = os.pipe()
            inf = os.fdopen(pipe[0], 'r')
                                    
            pid = os.fork()
            if (pid == 0):
                try:
                    os.execl(context.postcreate, context.postcreate, str(uid), str(gid), home)
                except OSError, e:
                    raise plugin.SplatPluginError, "Failed to execute post-creation script %s [Errno %d] %s." % (context.postcreate, e.errno, e.strerror)

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
            
            # Check if child process exited happily.
            if (status == 0):
                inf.close()
                return
            else:
                errstr = inf.readline()
                inf.close()
                raise plugin.SplatPluginError, "Post creation script %s %d %d %s exited abnormally: %s" % (context.postcreate, uid, gid, home, errstr)
