from setuptools import setup, find_packages

setup(
    name='cloud-resume-challenge-backend',
    version='0.1.0',
    description='Setting up a python package for backend of crc',
    long_description=open('README.md').read()
    author='Thomas S. Liu',
    author_email='thomas.s.liu@gmail.com',
    url='https://resume.thomasliu.click',
    packages=find_packages(include=['cloud-resume-challenge-backend', 'cloud-resume-challenge-backend.*'])
)