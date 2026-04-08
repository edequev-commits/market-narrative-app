#!/usr/bin/env sh
echo "PORT=$PORT"
python -m streamlit run dashboard.py --server.address=0.0.0.0 --server.port="${PORT}"
