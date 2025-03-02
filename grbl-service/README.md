# grbl-service for BierdeckelBot

This service is part of the **ServerBot** project and provides endpoints to control the CNC machine through its GRBL controller. It builds upon the solid foundation of the **BierdeckelBot** project, so please refer to it for more details and original setup.

### Table of Contents

- [Purpose](#purpose)
- [Installation & Running the Service](#installation--running-the-service)
- [Endpoints Overview](#endpoints-overview)
- [Acknowledgement of External Software](#acknowledgement-of-external-software)

## Purpose

The `grbl-service` offers an API to control the CNC machine by sending G-code commands to its GRBL controller. It requires that the computers is directly connected to the CNC machine via USB.

To communicate with the GRBL, `grbl-service` uses a command-line version of the **Universal Gcode Sender (UGS)**, named `UniversalGcodeSender.jar` in this folder.

## Installation & Running the Service

### Step 1: CNC Machine Setup

1. Connect the CNC machine to the computer via a USB cable. This service was developed for a **Genmitsu 3020-PRO MAX**, but should work with most GRBL-compatible CNC machines.
2. Find out the name of the USB port (e.g., `/dev/cu.usbserial-110` on macOS or COM on Windows) and the BAUD rate (typically `115200`) which is specific to your system. The BAUD rate can usually stay the default value, but the USB port is named differently on every device.

### Step 2: Install Dependencies & update PORT and BAUD_RATE

1. Ensure Python & Java are installed and active in your environment. Also ensure that you're in this directory (`grbl-service`)
2. Navigate to the `grbl-service` directory:

```
cd grbl-service
```

3. Install required Python packages with:

```
pip install -r requirements.txt
```

4. In `grbl-service.py`, set the correct port and BAUD rate for your CNC machine by updating the `PORT` and `BAUD_RATE` variables on lines 12 and 13.

### Step 3: Run the Service

Start the Flask app to run the service and expose the endpoints:

```
flask --app grbl-service.py run
```

If you wish to run the service on a specific port, use this command:

```
flask --app grbl-service.py run --port <desired-port>
```

## Endpoints Overview

This grbl-service offers several endpoints for controlling the CNC machine:

### 1. Home the CNC Machine

- **Endpoint**: `/home`
- **Method**: POST
- **Description**: Moves the CNC machine to its home position and sets the axes to 0. It rejects a request if the execution state `status` is set to `running`.

### 2. Move to Robot Access Position

- **Endpoint**: `/robot`
- **Method**: POST
- **Description**: Moves the CNC bed to the front for robot access by executing a predefined G-code file (`robot-position.gcode`).

### 3. Execute G-code Asynchronously

- **Endpoint**: `/executeGcode`
- **Method**: POST
- **Description**: Receives G-code, stores the provided callback URL, and executes the G-code asynchronously. Once execution is complete, it sends a PUT request to the callback URL. It rejects requests if the status is running.

## Acknowledgement of External Software

This service uses a CLI version of **Universal Gcode Sender (UGS)** to interact with the CNC machine. UGS is an open-source tool and the CLI version is available in this [GitHub repository](https://github.com/winder/Universal-G-Code-Sender/tree/master/ugs-cli).
