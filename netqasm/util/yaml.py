from yaml import dump, load

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper  # type: ignore
    from yaml import Loader  # type: ignore


def load_yaml(file_path):
    with open(file_path, "r") as f:
        data = load(f, Loader=Loader)
    return data


def dump_yaml(data, file_path):
    with open(file_path, "w") as f:
        dump(data, f, Dumper=Dumper)
