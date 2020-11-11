import os
from runpy import run_path
from datetime import datetime

from netqasm.logging.glob import get_netqasm_logger
from netqasm.util.yaml import load_yaml

logger = get_netqasm_logger()


def load_app_config_file(app_dir, app_name):
    ext = '.yaml'
    file_path = os.path.join(app_dir, f"{app_name}{ext}")
    if os.path.exists(file_path):
        config = load_yaml(file_path=file_path)
    else:
        config = None
    if config is None:
        return {}
    else:
        return config


def get_roles_config_path(app_dir):
    ext = '.yaml'
    file_path = os.path.join(app_dir, f'roles{ext}')
    return file_path


def load_roles_config(roles_config_file):
    if os.path.exists(roles_config_file):
        return load_yaml(roles_config_file)
    else:
        return None


def load_app_files(app_dir):
    app_tag = 'app_'
    ext = '.py'
    app_files = {}
    for entry in os.listdir(app_dir):
        if entry.startswith(app_tag) and entry.endswith('.py'):
            app_name = entry[len(app_tag):-len(ext)]
            app_files[app_name] = entry
    if len(app_files) == 0:
        raise ValueError(f"directory {app_dir} does not seem to be a application directory (no app_xxx.py files)")
    return app_files


def get_log_dir(app_dir):
    log_dir = os.path.join(app_dir, "log")
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
    return log_dir


def get_timed_log_dir(log_dir):
    now = datetime.now().strftime('%Y%m%d-%H%M%S')
    timed_log_dir = os.path.join(log_dir, now)
    if not os.path.exists(timed_log_dir):
        os.mkdir(timed_log_dir)
    return timed_log_dir


def get_post_function_path(app_dir):
    return os.path.join(app_dir, 'post_function.py')


def load_post_function(post_function_file):
    if not os.path.exists(post_function_file):
        return None
    return run_path(post_function_file)['main']


def get_results_path(timed_log_dir):
    return os.path.join(timed_log_dir, 'results.yaml')
