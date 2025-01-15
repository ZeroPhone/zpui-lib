#!/bin/bash -eux
rm -rf dist/*
nano pyproject.toml
python3 -m build
pip install -U dist/*.whl
python3 -m twine upload dist/*
python3 -m build
