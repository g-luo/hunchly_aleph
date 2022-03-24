"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""
import sys
sys.setrecursionlimit(1500)
from setuptools import setup

APP = ['HunchlyAleph.py']
DATA_FILES = []
OPTIONS = {
	'iconfile': 'icon.icns'
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
