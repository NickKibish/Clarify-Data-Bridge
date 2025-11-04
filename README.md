# Clarify Data Bridge for Home Assistant

A Home Assistant integration that collects sensor data from your smart home (temperature, humidity, energy consumption, etc.) and streams it to Clarify.io for advanced time-series visualization and collaboration.

## What it does

This integration automatically gathers data from your Home Assistant sensors and devices, then sends it to Clarify.io using their JSON-RPC API. Unlike basic Home Assistant dashboards, Clarify.io provides industrial-grade time-series analytics, mobile access, and team collaboration features - perfect for analyzing your home's energy usage, climate patterns, and IoT device performance over time.

## Installation

### HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Search for "Clarify Data Bridge" in HACS
3. Click Install
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/clarify_data_bridge` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings -> Devices & Services
2. Click "+ Add Integration"
3. Search for "Clarify Data Bridge"
4. Enter your Clarify API credentials:
   - **API Key**: Your Clarify API key from [Clarify dashboard](https://clarify.io)
   - **Integration ID**: Your Clarify integration ID

## Getting Clarify Credentials

1. Sign up for a free account at [clarify.io](https://clarify.io)
2. Create a new integration in your Clarify dashboard
3. Copy the API Key and Integration ID

## Features

- Automatic sensor data collection from Home Assistant
- Real-time streaming to Clarify.io
- Support for various sensor types (temperature, humidity, energy, etc.)
- Configurable update intervals
- Error handling and reconnection logic

## Requirements

- Home Assistant 2024.1.0 or newer
- Clarify.io account (free tier available)
- Python 3.11 or newer

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/NickKibish/clarify-data-bridge/issues).

## License

MIT License - See LICENSE file for details
