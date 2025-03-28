# Bittensor Subnet Lister

A simple command-line tool to list all subnets on the Bittensor network.

## Overview

This tool connects to the Bittensor network and displays information about all available subnets including:

- Subnet ID and name
- Symbol and token price
- Number of validators and miners
- Emission values (TAO/day)

## Requirements

- Python 3.8+
- Bittensor SDK 9.0.0+

## Installation

```bash
# Clone the repository
git clone https://github.com/Graytensor/bittensor-subnets-lister.git
cd bittensor-subnets-lister

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Basic usage (connects to Finney mainnet)
python src/list_subnets.py

# Save output to a JSON file
python src/list_subnets.py --output results.json

# Connect to testnet
python src/list_subnets.py --network test

# Connect to a custom endpoint
python src/list_subnets.py --endpoint ws://your.custom.node:9944

# Show debugging information
python src/list_subnets.py --debug

# Perform deep inspection of emission values
python src/list_subnets.py --deep
```

## Features

- **Dynamic TAO Support**: Compatible with Bittensor 9.0+ and the Dynamic TAO update
- **Robust Data Retrieval**: Falls back to alternative methods if primary API calls fail
- **Terminal-friendly**: Handles special Unicode characters properly
- **Export to JSON**: Save results for further analysis

## License

MIT

---
Created by Graytensor
https://graytensor.com/

Taotrack
https://taotrack.com/