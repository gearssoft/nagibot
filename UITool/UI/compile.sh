#!/bin/bash

pyside6-uic StartupWindow.ui -o StartupWindow.py
pyside6-uic mainForm.ui -o mainForm.py
pyside6-uic setupForm.ui -o setupForm.py
pyside6-uic StartUpForm.ui -o StartUpForm.py

echo "Done"
 
