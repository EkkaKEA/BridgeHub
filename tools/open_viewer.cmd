@echo off
title BridgeHub Viewer
cd /d "%~dp0.."
streamlit run tools\viewer.py
