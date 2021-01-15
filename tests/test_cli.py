import json
import os
from click.testing import CliRunner

import netqasm
from netqasm.runtime.cli import cli
from netqasm.runtime.env import EXAMPLE_APPS_DIR
from netqasm.util.yaml import load_yaml

TEMPLATE_EXAMPLE_NAME = "teleport"
TEMPLATE_EXAMPLE_DIR = os.path.join(EXAMPLE_APPS_DIR, TEMPLATE_EXAMPLE_NAME)

IGNORED_FILES = [
    "__init__.py",
    "__pycache__",
    "log",
    "cysignals_crash_logs",
]


def test_version():
    runner = CliRunner()
    results = runner.invoke(cli, "version")
    print(results.output)
    assert results.exit_code == 0
    assert results.output.strip() == netqasm.__version__


def test_new():
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = "test"
        results = runner.invoke(cli, ["new", path])
        print(results.output)
        assert results.exit_code == 0
        assert results.output.startswith("Creating application")
        assert TEMPLATE_EXAMPLE_NAME in results.output
        expected_files = [f for f in os.listdir(TEMPLATE_EXAMPLE_DIR) if f not in IGNORED_FILES]
        assert sorted(os.listdir(path)) == sorted(expected_files)


def test_quiet():
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = "test"
        results = runner.invoke(cli, ["new", "-q", path])
        print(results.output)
        assert results.exit_code == 0
        assert results.output == ""


def test_new_existing():
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = "test"
        results = runner.invoke(cli, ["new", path])
        assert results.exit_code == 0
        results = runner.invoke(cli, ["new", path])
        print(results.output)
        assert results.exit_code != 0
        assert "already exists" in results.output


def test_new_template():
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = "test"
        template = "anonymous_transmission"
        template_example_dir = os.path.join(EXAMPLE_APPS_DIR, template)
        results = runner.invoke(cli, ["new", path, f"--template={template}"])
        print(results.output)
        assert results.exit_code == 0
        assert results.output.startswith("Creating application")
        assert template in results.output
        expected_files = [f for f in os.listdir(template_example_dir) if f not in IGNORED_FILES]
        assert sorted(os.listdir(path)) == sorted(expected_files)


def test_init():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create template
        path = 'test'
        results = runner.invoke(cli, ["new", path])
        results.exit_code == 0
        files_start = os.listdir(path)
        # Remove all config files
        for entry in os.listdir(path):
            if not (entry.startswith("app_") and entry.endswith(".py")):
                os.remove(os.path.join(path, entry))
        assert len(os.listdir(path)) == 2

        # Initialize again
        results = runner.invoke(cli, ["init", f"--path={path}"])
        print(results.output)
        assert results.exit_code == 0
        # Check that it's the same number of files again
        assert sorted(os.listdir(path)) == sorted(files_start)

        # Check content based on teleport example
        expected_nodes = ["sender", "receiver"]
        # network
        network = load_yaml(os.path.join(path, "network.yaml"))
        assert "nodes" in network
        nodes = [node["name"] for node in network["nodes"]]
        assert sorted(expected_nodes) == sorted(nodes)
        assert "links" in network
        assert len(network["links"]) == 1
        # roles
        roles = load_yaml(os.path.join(path, "roles.yaml"))
        assert sorted(expected_nodes) == sorted(roles.keys())
        # input
        sender_input = load_yaml(os.path.join(path, "sender.yaml"))
        assert "phi" in sender_input
        assert "theta" in sender_input
        receiver_input = load_yaml(os.path.join(path, "receiver.yaml"))
        assert len(receiver_input) == 0


def test_init_not_app_dir():
    runner = CliRunner()
    with runner.isolated_filesystem():
        results = runner.invoke(cli, ["init"])
        print(results.output)
        print(results.exc_info)
        assert isinstance(results.exception, ValueError)
        assert "does not seem to be" in str(results.exception)
        assert results.exit_code != 0


def test_init_no_overwrite():
    runner = CliRunner()
    with runner.isolated_filesystem():
        path = "test"
        results = runner.invoke(cli, ["new", path])
        # Write test to all files
        for entry in os.listdir(path):
            with open(os.path.join(path, entry), 'w') as f:
                f.write("test")

        results = runner.invoke(cli, ["init", f"--path={path}"])
        assert results.exit_code == 0
        assert results.output.startswith("No files needed to be added")

        # Check that files remained
        for entry in os.listdir(path):
            with open(os.path.join(path, entry), 'r') as f:
                assert f.read() == "test"


def test_qne_login():
    """Test logging into the QNE produces a token."""
    from netqasm.runtime.cli import QNE_FOLDER_PATH, _login
    runner = CliRunner()
    try:
        username = os.environ['QNE_TEST_USER']
        password = os.environ['QNE_TEST_PWD']
    except AttributeError:
        # We allow this test to fail if the variables aren't set.
        return
    api_file = f'{QNE_FOLDER_PATH}/api_token'
    with runner.isolated_filesystem():
        assert not os.path.exists(api_file)
        for args in [(username, ''),
                     ('', password),
                     (True, password),
                     (username, True),
                     (username, password, True)]:
            try:
                _login(*args)
            except (ValueError, TypeError):
                assert not os.path.exists(api_file)
        # Test authentication doesn't crash if invalid credentials are supplied.
        results = runner.invoke(cli, ['qne', 'login'], input=f'{username}\nwrongpass\n')
        assert results.exit_code == 0
        assert not os.path.exists(api_file)
        # Test we can authenticate successfully
        results = runner.invoke(cli, ['qne', 'login'], input=f'{username}\n{password}\n')
        assert results.exit_code == 0
        assert os.path.exists(api_file)
        with open(api_file) as f:
            api_token = json.load(f)
        assert username == list(api_token.values())[0][0]
        # Test we get new tokens
        results = runner.invoke(cli, ['qne', 'login'], input=f'{username}\n{password}\n')
        assert results.exit_code == 0
        with open(api_file) as f:
            new_api_token = json.load(f)
        assert username == list(new_api_token.values())[0][0]
        assert api_token != new_api_token
        # Test we can run in verbose mode
        results = runner.invoke(cli, ['--verbose', 'qne', 'login'], input=f'{username}\n{password}\n')
        assert results.exit_code == 0


def test_qne_logout():
    """Test logging out."""
    from netqasm.runtime.cli import QNE_FOLDER_PATH
    runner = CliRunner()
    try:
        username = os.environ['QNE_TEST_USER']
        password = os.environ['QNE_TEST_PWD']
    except AttributeError:
        # We allow this test to fail if the variables aren't set.
        return
    with runner.isolated_filesystem():
        # Create an API token
        results = runner.invoke(cli, ['qne', 'login'], input=f'{username}\n{password}\n')
        assert results.exit_code == 0
        assert os.path.exists(f'{QNE_FOLDER_PATH}/api_token')
        # Test API token is destroyed when logged out.
        results = runner.invoke(cli, ['qne', 'logout'])
        assert results.exit_code == 0
        assert not os.path.exists(f'{QNE_FOLDER_PATH}/api_token')
        # Test logging out when already logged out doesn't crash.
        results = runner.invoke(cli, ['qne', 'logout'])
        assert results.exit_code == 0
        assert not os.path.exists(f'{QNE_FOLDER_PATH}/api_token')
