from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("netqasm")
except PackageNotFoundError:
    # package is not installed
    pass
