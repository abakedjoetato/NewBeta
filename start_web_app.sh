#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

# Make sure the required directories exist
mkdir -p templates static/css static/js

# Run the Flask web application
python main.py