from setuptools import setup, find_packages

setup(
    name='cloud-resume-challenge-backend',
    version='0.1.2',
    description='Setting up a python package for backend of crc',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Thomas S. Liu',
    author_email='thomas.s.liu@gmail.com',
    url='https://resume.thomasliu.click',
    packages=find_packages(include=['visitor', 'visitor.*']),
    python_requires='>=3.13',
    classifiers=[
        'Programming Language :: Python :: 3.13',
        'Operating System :: OS Independent',
    ]
)