from distutils.core import setup
from os.path import join, dirname, realpath

# Use version number of linkplayctl client module as version number for package
version_file = join(dirname(realpath(__file__)), 'linkplayctl', '_version.py')
exec(open(version_file).read())

setup(
    name="Linkplayctl",
    version=__version__, # From linkplayctl
    description="Simple client for controlling LinkPlay devices",
    author="Kurt Meinz",
    url="",
    py_modules=['linkplayctl'],
)
