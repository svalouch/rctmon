# -*- coding: utf-8 -*-
'''
Setuptools entrypoint
'''
from setuptools import setup  # type: ignore

with open('README.md', 'rt') as fh:
    long_description = fh.read()

setup(
    name='rctmon',
    version='0.0.2',
    author='Stefan Valouch',
    author_email='svalouch@valouch.com',
    description='Extracts data from RCT inverters',
    long_description=long_description,
    long_description_content_type='text/markdown',
    project_urls={
        'Source': 'https://github.com/svalouch/rctmon/',
        'Tracker': 'https://github.com/svalouch/rctmon/issues',
    },
    packages=['rctmon'],
    package_data={'rctmon': ['py.typed']},
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    url='https://github.com/svalouch/rctmon/',
    python_requires='>=3.7',

    install_requires=[
        'click',
        'influxdb-client',
        'prometheus_client>=0.9.0',
        'pydantic>=1.2',
        'pyyaml',
        'rctclient==0.0.3',
        'requests>=2.21',
        'paho-mqtt>=1.6'
    ],
    extras_require={
        'dev': [
            'mypy',
            'pylint',
        ],
        'docs': [
            'Sphinx>=2.0',
            'sphinx-autodoc-typehints',
            'sphinx-click',
            'sphinx-rtd-theme',
            'recommonmark>=0.5.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'rctmon=rctmon.cli:cli',
        ],
    },

    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)
