@echo off
TITLE TASI Buffett Agent
cd /d "F:\TASI_WarrenBuffettAgent"
echo Running TASI Agent...
py tasi_ranker.py
echo Generating Report...
py generate_report.py
pause
