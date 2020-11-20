from yaml import load, dump
try:
    from yaml import CLoader as Loader
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Loader  # type: ignore
    from yaml import Dumper  # type: ignore


def load_yaml(file_path):
    with open(file_path, 'r') as f:
        data = load(f, Loader=Loader)
    return data


def dump_yaml(data, file_path):
    with open(file_path, 'w') as f:
        dump(data, f, Dumper=Dumper)
