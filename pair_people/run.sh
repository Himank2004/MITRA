#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${YELLOW}  MITRA User Group Matching Server${NC}"
echo -e "${GREEN}=========================================${NC}"

# Check for embeddings directory
if [ ! -d "../User_Embeddings" ]; then
    echo -e "${YELLOW}Warning: User_Embeddings directory not found${NC}"
    echo -e "${YELLOW}Creating User_Embeddings directory...${NC}"
    mkdir -p "../User_Embeddings"
fi

# Check if requirements are installed
echo -e "${YELLOW}Checking requirements...${NC}"
if ! pip list | grep -q "flask"; then
    echo -e "${YELLOW}Installing requirements...${NC}"
    pip install -r requirements.txt
fi

# Set development mode for better debugging
export FLASK_ENV=development

# Start the server
echo -e "${GREEN}Starting group matching server...${NC}"
echo -e "${GREEN}Server will be available at http://localhost:5000${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"

python server.py 