import setuptools

if __name__ == "__main__":
    setuptools.setup(
        packages=setuptools.find_packages(exclude=("tests", "docs", "examples")),
        package_data={
            "netqasm": [f"examples/apps/*/{file}" for file in ["README.md", "*.yaml"]]
        },
    )
