#!/usr/bin/env python

# upi: mbea966
# name: Madeleine Beagley

from __future__ import with_statement

import logging
import os
import sys
import errno
import filecmp
import glob
import re

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn
from shutil import copy2

class VersionFS(LoggingMixIn, Operations):
    def __init__(self):
        # get current working directory as place for versions tree
        self.root = os.path.join(os.getcwd(), '.versiondir')
        # check to see if the versions directory already exists
        if os.path.exists(self.root):
            print 'Version directory already exists.'
        else:
            print 'Creating version directory.'
            os.mkdir(self.root)

    # Helpers
    # =======

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    def notHidden(self, path):
        if (os.path.basename(path).startswith('.')):
            return False
        return True


    # Filesystem methods
    # ==================


    # can we access this path?
    def access(self, path, mode):
        # print "access:", path, mode
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        # print "chmod:", path, mode
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        # print "chown:", path, uid, gid
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)


    def getattr(self, path, fh=None):
        # print "getattr:", path
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    #need to modify. goes through and looks throiugh current dir and reads filenames
    def readdir(self, path, fh):
        # print "readdir:", path
        full_path = self._full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            # only display files in mount that are not hidden
            if (self.notHidden(r)):
                yield r

    def readlink(self, path):
        # print "*******************readlink:", path
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        # print "mknod:", path, mode, dev
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        # print "rmdir:", path
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        # print "mkdir:", path, mode
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        # print "statfs:", path
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        # print "unlink:", path
        return os.unlink(self._full_path(path))

    def symlink(self, name, target):
        # print "symlink:", name, target
        return os.symlink(target, self._full_path(name))

    def rename(self, old, new):
        # print "rename:", old, new
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        # print "link:", target, name
        return os.link(self._full_path(name), self._full_path(target))

    def utimens(self, path, times=None):
        # print "utimens:", path, times
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        print '** open:', path, '**'
        full_path = self._full_path(path)

        # store a temp file with initial content of opened file if it is not hidden
        if (self.notHidden(full_path)):
            copy2(full_path, full_path + '_tmp')

        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        print '** create:', path, '**'
        full_path = self._full_path(path)

        # make an empty temp file if created file is not hidden
        if (self.notHidden(full_path)):
            os.open(full_path + '_tmp', os.O_WRONLY | os.O_CREAT, mode)

        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        print '** read:', path, '**'
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        print '** write:', path, '**'
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        print '** truncate:', path, '**'
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        print '** flush', path, '**'
        return os.fsync(fh)


    def newVersion(self, path, fh):
        versionFilePath = self.root + '/.' + os.path.basename(path)
        filePath = self._full_path(path)

        # find all the versions of the current file and sort oldest to newest
        versions = sorted(glob.glob(versionFilePath + '.*'))
        versions.reverse()

        # delete the oldest version to make room for new version
        if (len(versions) == 6):
            # oldest version is version with largest version number
            oldest = versions.pop(0)
            os.remove(oldest)

        # increment the version number for each version
        for version in versions:
            # extract version number from filename
            ints = re.findall(r'\d+', version)
            versionNum = ints[len(ints) - 1]

            # increment version number
            newVersionNum = int(versionNum) + 1

            # rename the version with incremented version number
            os.rename(version, versionFilePath + '.' + str(newVersionNum))

        # store the most recent version as first version
        copy2(filePath, versionFilePath + '.1')


    def release(self, path, fh):
        print '** release', path, '**'
        tempPath = self._full_path(path) + '_tmp'

        # if the file has been opened and changed, it must be saved
        if (os.path.isfile(tempPath)):
            # compare state of temp and current version of file
            if not (filecmp.cmp(self._full_path(path), tempPath)):
                # make a new version of the file
                self.newVersion(path, fh)

            # temp files must be wiped after each release
            os.remove(tempPath)

        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        print '** fsync:', path, '**'
        return self.flush(path, fh)


def main(mountpoint):
    FUSE(VersionFS(), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    #logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1])
