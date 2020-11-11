import setuptools

with open("README.md", 'r') as f:
    long_description = f.read()

with open("requirements.txt", 'r') as f:
    install_requires = [line.strip() for line in f.readlines()]

setuptools.setup(
    long_description=long_description,
    long_description_content_type="text/markdown",
    include_package_data=True,
    packages=setuptools.find_packages(exclude=('tests', 'docs', 'examples')),
    install_requires=install_requires,
    python_requires='>=3.7',
    entry_points='''
        [console_scripts]
        netqasm=netqasm.runtime.cli:cli
    '''
)
