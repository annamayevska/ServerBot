# grbl-service for BierdeckelBot
This service is part of the **BierdeckelBot** project and provides endpoints to control the CNC machine through its GRBL controller. For more on the **BierdeckelBot** project, including its background and architecture, refer to the [main README](/README.md) in the root folder.

### Table of Contents
- [Purpose](#purpose)
- [Installation & Running the Service](#installation--running-the-service)
- [Endpoints Overview](#endpoints-overview)
- [Troubleshooting & General Remarks](#troubleshooting--general-remarks)
- [Acknowledgement of External Software](#acknowledgement-of-external-software)


## Purpose
The `grbl-service` offers an API to control the CNC machine by sending G-code commands to its GRBL controller. Therefore it needs to run on a computer directly connected to the CNC machine via USB.

To communicate with the GRBL, `grbl-service` uses a command-line version of the **Universal Gcode Sender (UGS)**, named `UniversalGcodeSender.jar` in this folder. A pre-built Java version is included in this directory, but the latest version can be found in this [GitHub repository](https://github.com/winder/Universal-G-Code-Sender/tree/master/ugs-cli).

The code is straightforward and thoroughly commented, so this guide focuses only on installation, configuration, and an overview of endpoints.

Note that the grbl-service can also be used as a standalone service outside of the BierdeckelBot-setting, if you wish to remote-control any GRBL-controlled machine.

## Installation & Running the Service
### Step 1: CNC Machine Setup
1. Connect the CNC machine to the computer via a USB cable. This service was developed for a **Genmitsu 3020-PRO MAX**, but should work with most GRBL-compatible CNC machines.
2. Find out the name of the USB port (e.g., `/dev/cu.usbserial-110` on macOS) and the BAUD rate (typically `115200`) which is specific to your system. The BAUD rate can usually stay the default value, but the USB port is named differently on every device.

*Tip:* You can use the regular UGS software with a graphic UI to identify the USB port in use. If you connect your machine via USB, it shows you the name of the USB port, where a GRBL-machine is currently connected.

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
- **Description**: Moves the CNC machine to its home position and sets the axes to 0. This should be done before any G-code execution to ensure calibrated axes. It rejects a request if the execution state `status` is set to `running`.
- **Note**: Synchronous endpoint, meaning that it waits for the homing process to complete before returning a response.

### 2. Move to Robot Access Position
- **Endpoint**: `/robot`
- **Method**: POST
- **Description**: Moves the CNC bed to the front for robot access by executing a predefined G-code file (`robot-position.gcode`). It also rejects a request if the `status` is set to `running`.
- **Note**: Synchronous endpoint, meaning that it waits for the execution to complete before returning a response.

### 3. Execute G-code Asynchronously
- **Endpoint**: `/executeGcode`
- **Method**: POST
- **Description**: Executes G-code passed in the request (x-www-form-urlencoded or JSON) on the machine. The G-code is temporarily saved as a file and deleted after execution. It also rejects requests, if the `status` is set to `running`.
- **Required Parameters**:
    - `gcode`: Full G-code, including necessary parameters (e.g., Feedrate).
- **Note**: Asynchronous endpoint, meaning that is starts UGS in a separate thread and sets `status` to `running`, to signal a running process.

### 4. Retrieve Status
- **Endpoint**: `/status`
- **Method**: GET
- **Description**: Returns the `status` value (`available` or `running`), enabling asynchronous G-code execution by allowing the CPEE to monitor machine availability.

## General Remarks
- This service always opens a connection for each request and closes it after successful execution. Thus, only one execution at a time is possible, which is also the reason for the execution state `status`. All endpoints check this status first and then behave accordingly, to prevent errors from two parallel executions.
- Please note that the service (or specifically the CLI-UGS) only works, if nothing else is connected to the GRBL. So if you have the regular UGS running on your computer, make sure that you're not connected to the GRBL

## Acknowledgement of External Software
This service uses a CLI version of **Universal Gcode Sender (UGS)** to interact with the CNC machine. UGS is an open-source tool and the CLI version is available in this [GitHub repository](https://github.com/winder/Universal-G-Code-Sender/tree/master/ugs-cli). 

It's a very valuable tool and made this project possible in the first place. So I thank all contributors for the program!
