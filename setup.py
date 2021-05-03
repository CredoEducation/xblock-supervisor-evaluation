# -*- coding: utf-8 -*-

# Imports ###########################################################

import os
from setuptools import setup


# Functions #########################################################

def package_data(pkg, root_list):
    """Generic function to find package_data for `pkg` under `root`."""
    data = []
    for root in root_list:
        for dirname, _, files in os.walk(os.path.join(pkg, root)):
            for fname in files:
                data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}


# Main ##############################################################

setup(
    name='xblock-supervisor-evaluation',
    version='1.0.0',
    description='XBlock - Supervisor Evaluation',
    packages=['supervisor_evaluation'],
    install_requires=[
        'XBlock',
        'xblock-utils',
    ],
    entry_points={
        'xblock.v1': 'supervisor-evaluation = supervisor_evaluation:SupervisorEvaluationBlock',
    },
    package_data=package_data("supervisor_evaluation", ["static", "templates", "public"]),
)
