# Copyright (c) 2013, Aaron Gallagher <_@habnab.it>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.

"""Simplify your python project versioning.

In-depth docs online: https://vcversioner.readthedocs.org/en/latest/
Code online: https://github.com/habnabit/vcversioner

"""

from __future__ import print_function, unicode_literals

import collections
import os
import subprocess


Version = collections.namedtuple('Version', 'version commits sha')


_print = print
def print(*a, **kw):
    _print('vcversioner:', *a, **kw)


def _fix_path(p):
    "Translate ``/``s into the right path separator."
    return p.replace('/', os.sep)


def find_version(include_dev_version=True, root='%(pwd)s',
                 version_file='%(root)s/version.txt', version_module_paths=(),
                 git_args=('git', '--git-dir', '%(root)s/.git', 'describe',
                           '--tags', '--long'),
                 Popen=subprocess.Popen, open=open):
    """Find an appropriate version number from version control.

    It's much more convenient to be able to use your version control system's
    tagging mechanism to derive a version number than to have to duplicate that
    information all over the place. Currently, only git is supported.

    The default behavior is to write out a ``version.txt`` file which contains
    the git output, for systems where git isn't installed or there is no .git
    directory present. ``version.txt`` can (and probably should!) be packaged
    in release tarballs by way of the ``MANIFEST.in`` file.

    :param include_dev_version: By default, if there are any commits after the
                                most recent tag (as reported by git), that
                                number will be included in the version number
                                as a ``.dev`` suffix. For example, if the most
                                recent tag is ``1.0`` and there have been three
                                commits after that tag, the version number will
                                be ``1.0.dev3``. This behavior can be disabled
                                by setting this parameter to ``False``.

    :param root: The directory of the repository root. The default value is the
                 current working directory, since when running ``setup.py``,
                 this is often (but not always) the same as the current working
                 directory. Standard substitutions are performed on this value.

    :param version_file: The name of the file where version information will be
                         saved. Reading and writing version files can be
                         disabled altogether by setting this parameter to
                         ``None``. Standard substitutions are performed on this
                         value.

    :param version_module_paths: A list of python modules which will be
                                 automatically generated containing
                                 ``__version__`` and ``__sha__`` attributes.
                                 For example, with ``package/_version.py`` as a
                                 version module path, ``package/__init__.py``
                                 could do ``from package._version import
                                 __version__, __sha__``.

    :param git_args: The git command to run to get a version. By default, this
                     is ``git --git-dir %(root)s/.git describe --tags --long``.
                     ``--git-dir`` is used to prevent contamination from git
                     repositories which aren't the git repository of your
                     project. Specify this as a list of string arguments
                     including ``git``, e.g. ``['git', 'describe']``. Standard
                     substitutions are performed on each value in the provided
                     list.

    :param Popen: Defaults to ``subprocess.Popen``. This is for testing.

    :param open: Defaults to ``open``. This is for testing.

    *root*, *version_file*, and *git_args* each support some substitutions:

    ``%(root)s``
      The value provided for *root*. This is not available for the *root*
      parameter itself.

    ``%(pwd)s``
      The current working directory.

    ``/`` will automatically be translated into the correct path separator for
    the current platform, such as ``:`` or ``\``.

    """

    substitutions = {'pwd': os.getcwd()}
    substitutions['root'] = root % substitutions
    git_args = [_fix_path(arg % substitutions) for arg in git_args]
    if version_file is not None:
        version_file = _fix_path(version_file % substitutions)

    # try to pull the version from git, or (perhaps) fall back on a
    # previously-saved version.
    try:
        proc = Popen(git_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        raw_version = None
        git_output = []
    else:
        stdout, stderr = proc.communicate()
        raw_version = stdout.strip().decode()
        git_output = stderr.decode().splitlines()
        version_source = 'git'

    def show_git_output():
        if not git_output:
            return
        print('-- git output follows --')
        for line in git_output:
            print(line)

    # git failed if the string is empty
    if not raw_version:
        if version_file is None:
            print('%r failed.' % (git_args,))
            show_git_output()
            raise SystemExit(2)
        elif not os.path.exists(version_file):
            print("%r failed and %r isn't present." % (git_args, version_file))
            print("are you installing from a github tarball?")
            show_git_output()
            raise SystemExit(2)
        with open(version_file, 'rb') as infile:
            raw_version = infile.read().decode()
        version_source = repr(version_file)


    # try to parse the version into something usable.
    try:
        tag_version, commits, sha = raw_version.rsplit('-', 2)
    except ValueError:
        print("%r (from %s) couldn't be parsed into a version." % (
            raw_version, version_source))
        show_git_output()
        raise SystemExit(2)

    if version_file is not None:
        with open(version_file, 'w') as outfile:
            outfile.write(raw_version)

    if commits == '0' or not include_dev_version:
        version = tag_version
    else:
        version = '%s.dev%s' % (tag_version, commits)

    for path in version_module_paths:
        with open(path, 'w') as outfile:
            outfile.write("""
# This file is automatically generated by setup.py.
__version__ = %s
__sha__ = %s
""" % (repr(version).lstrip('u'), repr(sha).lstrip('u')))

    return Version(version, commits, sha)


def setup(dist, attr, value):
    """A hook for simplifying ``vcversioner`` use from distutils.

    This hook, when installed properly, allows vcversioner to automatically run
    when specifying a ``vcversioner`` argument to ``setup``. For example::

      from setuptools import setup

      setup(
          setup_requires=['vcversioner'],
          vcversioner={},
      )

    The parameter to the ``vcversioner`` argument is a dict of keyword
    arguments which :func:`find_version` will be called with.

    """

    dist.version = dist.metadata.version = find_version(**value).version
