#!/bin/bash

set -e

echo "Starting all services..."
brew services start mongodb-community@6.0  &

echo "Starting TherapyBot API..."
cd ML_Backend/TherapyBot
./start_api.sh &

echo "Starting Backend..."
cd ../../Backend
npm run dev &

echo "Starting Frontend..."
cd ../frontend
npm start

wait