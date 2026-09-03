@echo off
REM Wrapper: everything lives in test.py so macOS, Linux and Windows run the same code.
python "%~dp0test.py" %*
