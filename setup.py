from setuptools import setup

setup(name='caurus',
      version='0.1.0',
      description='verification scheme based on 2D barcodes',
      long_description=open('README.md').read(),
      long_description_content_type='text/markdown',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: Security',
      ],
      keywords='barcode mfa tfa verification',
      url='http://github.com/george-hopkins/caurus',
      author='George Hopkins',
      author_email='george-hopkins@null.net',
      license='MIT',
      packages=['caurus'],
      entry_points={
          'console_scripts': ['caurus=caurus.cli:main'],
      },
      install_requires=[
          'bitstring',
          'crcmod',
          'cryptography',
          'svgwrite',
          'reedsolo',
      ],
      zip_safe=False)
