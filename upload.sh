#!/bin/bash -eux

rm -rf dist/*
nano pyproject.toml
git add pyproject.toml
python3 -m build
pip install -U --force-reinstall dist/*.whl
if [ ${1-default} != "local" ] ; then
    python3 -m twine upload dist/*
fi
