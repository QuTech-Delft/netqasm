import setuptools

with open("requirements.txt", "r") as f:
    install_requires = [line.strip() for line in f.readlines()]

with open("test_requirements.txt", "r") as f:
    install_requires += [line.strip() for line in f.readlines()]

if __name__ == "__main__":
    setuptools.setup(
        packages=setuptools.find_packages(exclude=("tests", "docs", "examples")),
        package_data={
            "netqasm": [
                f"examples/apps/*/{file}" for file in ["README.md", "*.yaml", "*.json"]
            ]
        },
        install_requires=install_requires,
    )
