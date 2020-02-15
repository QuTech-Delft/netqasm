import setuptools

with open("README.md", 'r') as f:
    long_description = f.read()

with open("requirements.txt", 'r') as f:
    install_requires = [line.strip() for line in f.readlines()]

setuptools.setup(
    name="netqasm",
    version="0.0.0",
    author="Axel Dahlberg",
    author_email="e.a.dahlberg@tudelft.nl",
    description="Tool for parsing, encoding, decoding and executing NetQASM subroutines",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.tudelft.nl/qinc-wehner/NetQASM/NetQASM",
    include_package_data=True,
    packages=setuptools.find_packages(exclude=('tests', 'docs', 'examples')),
    install_requires=install_requires,
    python_requires='>=3.6',
    entry_points='''
        [console_scripts]
        netqasm=netqasm.cli:cli
    '''
)
