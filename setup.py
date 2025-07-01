__tooling_name__ = "CostMinimizer"

import os

from setuptools import setup, find_packages

version = '0.0.1'
description = f'Cost Optimization tooling for Customers ({__tooling_name__}) Tooling'

# Declare your non-python data files:
# Files underneath configuration/ will be copied into the build preserving the
# subdirectory structure if they exist.
data_files = []
for root, dirs, files in os.walk("configuration"):
    data_files.append(
        (os.path.relpath(root, "configuration"), [os.path.join(root, f) for f in files])
    )

discovered_packages = find_packages(where='src/CostMinimizer', include=['CostMinimizer', 'CostMinimizer.*'])
discovered_packages.append('CostMinimizer')

setup(
    name='CostMinimizer',
    version=version,
    description=description,
    author='CostMinimizer Tooling Team',
    maintainer_email='slepetre@amazon.com',
    author_email='aws-co-tooling-core@amazon.com',
    url='https://github.com/aws-samples/sample-costminimizer.git',
    package_dir= { '': 'src/'},
    packages=discovered_packages,
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'CostMinimizer=CostMinimizer.CostMinimizer:main'
            ]
    },
)

print(discovered_packages)