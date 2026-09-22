#!/usr/bin/env python3
"""Dry-run stand-in for pi: writes the oracle-conformant stub files for one tool."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures

ws, tool = sys.argv[1], sys.argv[2]
fixtures.write_stub(tool, ws)
print("stub wrote files for", tool)
