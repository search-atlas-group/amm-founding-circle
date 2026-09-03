@echo off
REM Wrapper: everything lives in install.py so macOS, Linux and Windows run the same code.
python "%~dp0install.py" %*
