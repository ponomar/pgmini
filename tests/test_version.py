import os

import tomli

from pgmini import __version__


def test():
    with open(os.path.join(os.getcwd(), 'pyproject.toml'), 'rb') as f:
        obj = tomli.load(f)
    assert obj['tool']['poetry']['version'] == __version__
