
from setuptools import setup, find_packages


setup(
    name='myfpga',
    author='Zachary Crites',
    description='Synthesis toolchain for myfpga',
    version='0.0.1',
    packages=find_packages(exclude=['*.tests']),
    entry_points={
        'console_scripts': [
            'myfpga=myfpga.__main__:main',
        ],
    },
)
