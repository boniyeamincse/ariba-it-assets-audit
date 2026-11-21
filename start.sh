#!/bin/bash
# Convenient startup script for Akij IT Asset Audit System
echo "============================================================"
echo " Starting Akij Plastics IT Asset Audit System..."
echo " Open in Browser: http://localhost:9000/login/"
echo "============================================================"
python3 manage.py runserver 0.0.0.0:9000
