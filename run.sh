set -e
python probe.py 2>&1 | tee results/probe.txt
