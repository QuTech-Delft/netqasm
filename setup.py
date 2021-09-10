import setuptools

with open("requirements.txt", "r") as f:
    install_requires = [line.strip() for line in f.readlines()]

if __name__ == "__main__":
    setuptools.setup(
        install_requires=install_requires,
        packages=setuptools.find_packages(exclude=("tests", "docs", "examples")),
        package_data={
            "netqasm": [f"examples/apps/*/{file}" for file in ["README.md", "*.yaml"]]
        },
    )
