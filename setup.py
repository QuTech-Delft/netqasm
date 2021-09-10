import setuptools

with open("requirements.txt", "r") as f:
    install_requires = [line.strip() for line in f.readlines()]

if __name__ == "__main__":
    setuptools.setup(install_requires=install_requires)
