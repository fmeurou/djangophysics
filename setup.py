#!/usr/bin/env python3
import os
import subprocess
from datetime import date

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()


def get_version(app):
    version = date.today().strftime('%Y-%m')
    git_tag = "0.0"
    git_commits = "0"
    suffix = "dev"
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"]
        ).rstrip().decode('utf8')
        git_describe = subprocess.check_output(
            ["git", "describe", "--long"]
        ).rstrip().decode('utf8')
        git_tag = git_describe.split('-')[0]
        git_commits = git_describe.split('-')[1]
        if branch == 'main':
            suffix = ''
        else:
            suffix = 'dev'
        print(branch, git_tag, git_commits, suffix)
        version = '{}.{}{}'.format(git_tag, git_commits, suffix)
    except (subprocess.CalledProcessError, OSError) as e:
        print('git not installed', e)
    try:
        fp = open('{}/version.py'.format(app), 'w')
        fp.write(
            'djangophysics_version = [{}, {}, "{}"]\n'.format(
                git_tag.replace('.', ', '), git_commits, suffix)
        )
        fp.close()
    except Exception:
        print('ERROR opening {}/__version__.py'.format(app), os.curdir)
    return version


module = 'djangophysics'

setup(
    name='djangophysics',
    description='Django APIs for physics conversion and calculations',
    python_requires='>3.7.0',
    version=get_version(module),
    author='Frédéric MEUROU',
    author_email='fm@peabytes.me',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://api.geophysics.io/swagger/',
    install_requires=[
        "Django>=3.2",
        "django-cors-headers>=3.2",
        "django-cors-middleware>=1.5",
        "django-createsuperuser",
        "django-extensions>=3.0",
        "django-filter>=2.3",
        "django-redis>=4.12",
        "django-sendfile>=0.3",
        "djangorestframework>=3.11",
        "drf-yasg>=1.17",
        "markdown>=3.0",
        "lxml>=4.0",
        "pysendfile>=2.0",
        "gunicorn",
        "requests",
        "pytz",
        "pycountry",
        "countryinfo>=0.1",
        "timezonefinder>=4.4",
        "iso4217",
        "forex-python>=1.0",
        "Babel>=2.8",
        "Pint>=0.17",
        "networkx>=2.5",
        "sympy>=1.7",
        "channels>=3.0",
        "uncertainties>=3.1",
        "ariadne>=0.13"
    ],
    extras_require={
        'mysql': ["mysql", ],
        'postgres': ['psycopg2',],
        'develop': ['jupyter', ]
    },
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "Environment :: Web Environment",
        "Development Status :: 5 - Production/Stable",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.0",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Scientific/Engineering :: Mathematics",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Office/Business",
        "License :: OSI Approved :: MIT License",
    ],
    py_modules=[
        'djangophysics.core',
        'djangophysics.countries',
        'djangophysics.currencies',
        'djangophysics.rates',
        'djangophysics.units',
        'djangophysics.converters',
        'djangophysics.calculations'
    ],
)
