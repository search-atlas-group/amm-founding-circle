@echo off
REM Wrapper: everything lives in uninstall.py so macOS, Linux and Windows run the same code.
python "%~dp0uninstall.py" %*
