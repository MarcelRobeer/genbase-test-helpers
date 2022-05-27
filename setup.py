 from setuptools import setup

 setup(
   name='test-helpers',
   version='0.1',
   author='Marcel Robeer',
   packages=['test-helpers'],
   description='Generic test helpers',
   install_requires=[
       "instancelib>=0.4.4.1",
   ],
)
