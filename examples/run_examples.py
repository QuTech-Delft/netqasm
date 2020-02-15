import os
import runpy
import inspect


def _has_first_argument(function, argument):
    """Checks if a function takes a named argument as the first argument"""
    argnames = inspect.getfullargspec(function).args
    return argnames[0] == "no_output"


def main():
    path_to_here = os.path.dirname(os.path.abspath(__file__))

    for root, folders, files in os.walk(path_to_here):
        for filename in files:
            if filename.startswith("example_") and filename.endswith(".py"):
                filepath = os.path.join(root, filename)
                members = runpy.run_path(filepath)
                if "main" in members:
                    main = members["main"]
                    if _has_first_argument(main, "no_output"):
                        main(no_output=True)
                    else:
                        print(f"The main function in {filename} does not take the argument 'no_output'")
                else:
                    print(f"The example {filename} does not have a main function")


if __name__ == "__main__":
    main()
