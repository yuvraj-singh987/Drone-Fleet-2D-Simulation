# Drone Fleet Management — 2D Simulation

A Python-based 2D simulation of a drone fleet management system for timed deliveries. The project explores package batching, delivery-route planning, battery feasibility, wind effects, and charging management.

## Features

* 2D graphical simulation using Pygame
* Multiple packages per drone trip, subject to maximum payload
* Delivery-order evaluation against package deadlines
* Payload-dependent drone airspeed
* Wind effects on ground speed and mission time
* Battery consumption and safety-reserve checks
* Drone states: idle, busy, and charging
* Charging-pad management and waiting queues
* Visualization of delivery routes and fleet status

## Technology Stack

* Python
* Pygame

## Installation

Clone the repository:

```bash
git clone https://github.com/yuvraj-singh987/Drone-Fleet-2D-Simulation.git
cd Drone-Fleet-2D-Simulation
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run the Simulation

```bash
python visual_simulation.py
```

## Configuration

Simulation parameters, including payload limits, speed assumptions, battery settings, and wind conditions, can be adjusted in the configuration file.

## Notes

This is a software simulation, not a connection to physical drones. Some physical models, such as the payload-speed relationship and energy-consumption factors, are configurable assumptions.

## Future Improvements

* More realistic drone movement and battery models
* Improved charging and task scheduling
* Live fleet monitoring dashboard
* Obstacle avoidance
* Communication-failure handling
* Additional test scenarios and performance evaluation

## Author

Yuvraj Singh
