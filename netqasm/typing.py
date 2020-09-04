import sys

if ((sys.version_info[0] == 3) and (sys.version_info[1] >= 8)) or (
    sys.version_info[0] >= 4
):
    from typing import TypedDict
elif (sys.version_info[0] == 3) and (sys.version_info[1] in [6, 7]):
    from typing_extensions import TypedDict
else:
    raise RuntimeError("Unsupported Python version, {0}".format(sys.version_info))
