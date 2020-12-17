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
