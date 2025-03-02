# ServerBot

The **ServerBot** is a process automation for serving ordered drinks with customized coasters. It streamlines the bar experience process by providing the interface for ordering a personalized drink, seamlessly transforming the order input details into G-code instructions that guide a CNC machine to draw them on a coaster; and serving the order consisting of the drink and the coaster altogether.

In this video you can observe the whole process: ![process video](/documentation/video.mp4)

## Contents

This README offers an overview of the ServerBot, including an explanation of its core processes and individual components.

- [Structure and components](#structure-and-components)
  - [CNC machine](#cnc-machine)
  - [Serving component](#serving-component)
  - [Robot arm](#robot-arm)
  - [Software components](#software-components)
  - [Additionally](#additionally)
- [Process](#process)
  - [Step 0:](#step-0)
  - [Step 1:](#step-1)
  - [Step 2:](#step-2)
  - [Step 3:](#step-3)
  - [Step 4:](#step-4)
  - [Step 5:](#step-5)
  - [Step 6:](#step-6)
  - [Step 7:](#step-7)
- [Process models](#process-models)
  - [Main process](#main-process)
  - [Subprocess](#subprocess)
- [Attributions](#attributions)
- [Contribution](#contribution)
- [Outlook](#outlook)

## Structure and components

### CNC machine:

[Genmitsu 3020-PRO MAX machine](https://www.amazon.de/dp/B0DF2NPKJH), expanded through the use of custom parts for the coaster, allowing to draw texts and images according to G-code instructions with an Edding sharpie.
![Image of the CNC machine](/documentation/photos/CNC_machine_atwork.jpg)

### Serving component:

a pedestal-like component modeled in [OnShape](https://www.onshape.com/en/) and created with a 3d printer that includes a recess with sloped inwards edges on top for the glass, and an inclined surface to lean the coaster onto for better visibility; the component is designed with a substantial void to optimize material efficiency by reducing plastic usage.
![Image of the serving component top](/documentation/photos/serving_component_top.jpg)
![Image of the serving component side](/documentation/photos/serving_component_side.jpg)

### Robot arm:

universal cobot set up in the laboratory that performs the physical tasks of the process such as inserting and retrieving the coaster from the CNC machine; positioning the glass into the recess and the coaster onto the leaned surface of the serving component.

### Software components

#### Interface:

Consists of 3 sections:

- Choose your drink: provides a menu to choose from
  ![Interface image](/documentation/photos/interface1.png)
- Choose your logo: provides a mutually exclusive opportunity to either select the image from a predefined library or to upload your own svg file
  ![Interface image](/documentation/photos/interface2.png)
- Enter the name: field for specifying the person who orders or any other text, restricted to 10 characters.
  ![Interface image](/documentation/photos/interface3.png)

#### 5 modularized services:

- **Order management service:** The service checks for any existing orders in the order directory. If orders have already been placed, it processes the first order by retrieving the name and logo information, then deletes the order from the directory. If no orders are found, it stores a callback and waits until an order is placed, ensuring the system continues to operate smoothly.
- **Order creation service:** When a new order is created, this service first checks for any available callbacks. If any callbacks are found, the order data is immediately sent to the first callback in the list. If no callbacks are available at the time, the order is stored in the orders directory for later processing.
- **Text to gcode conversion service:** This service is responsible for converting input text into G-code. It dynamically adjusts the font size based on the length of the text, ensuring that the text fits within the lower quarter of the coaster's height. It calculates the positioning and scaling of the text, ensuring it is centered within the designated area of the coaster.
- **Svg to gcode conversion service:** This service converts an SVG image into G-code. It first preprocesses the SVG to fit within the dimensions of the coaster, ensuring that the image is properly resized based on the coaster’s available area. The SVG is scaled proportionally to maintain its aspect ratio, and then aligned centrally within the upper three-quarters of the coaster’s height. After preprocessing, the service generates the G-code.

- **Grbl service:** This service controls a CNC machine connected to a computer, including moving the machine to the reference positions and executing G-code files. It ensures that only one operation is running at a time and allows asynchronous execution through threading.

### Additionally:

- [cardboard coasters](https://www.amazon.de/dp/B0BQJX9ZZK)
- Edding sharpie

## Process

### Step 0.

Launching all components: before starting the process, make sure that all the software services have been started, the CNC machine has been connected to the PC and turned on, the robot is set to the remote mode and the serving component is in the specified position.

#### Required software

- **Python**
- **Java** for text to G-code conversion
- **Rust** for svg to G-code conversion

#### Starting the services

Launch each of the services with

```
flask --app name-of-the-service run
```

#### Starting the frontend

Install Node dependencies:

```
cd frontend npm install
```

Launch the frontend:

```
npm start
```

#### Endpoints

**Endpoint**: `/manageOrders`

- **Method**: GET

**Endpoint**: `/createOrder`

- **Method**: POST

**Endpoint**: `/svg2gcode`

- **Method**: POST

**Endpoint**: `/text2gcode`

- **Method**: POST

#### GRBL service

A more detailed README along with elaboration on GRBL service **endpoints** can be found [separately](/grbl-service/README.md)

### Step 1.

Making an order: the user enters his choices in the interface and submits them through the place order button, getting visual feedback. Another orders can be submitted at any time during the process, and they would be stored in the orders directory for future use.
![Interface image](/documentation/photos/interface4.png)

### Step 2.

As a preparation measure, the CNC machine is homed to its reference position to ensure correct execution of G-codes later on.

### Step 3.

The order is either retrieved from the orders directory, or if the order has been just made, the process continues from this point, storing the name and logo information in the variables text and svg in the CPEE engine.

### Step 4.

The two inputs are consequently separately converted into G-code strings and stored in variables gcode1, gcode2 in the CPEE Engine.

### Step 5.

The CNC machine is moved forward and the robot arm takes out the coaster and puts it into drawing bed.

### Step 6.

Next is the parallel execution: while the two G-codes for text and svg are being drawn at the CNC machine, the robot arm is serving the glass into the recess on top of the serving component, thus reducing the time the process execution takes, utilizing two independent resources.
![Image of the created coasters](/documentation/photos/coasters.png)

### Step 7.

When the coaster is ready, and the robot is free for further use, he serves the coaster onto inclined surface of the serving component, finishing one loop of order processing.
![Image of the served drink](/documentation/photos/served_order.jpg)

## Process models

### Main process

The main model encapsulates all described activites, apart from serving the glass that is done in parallel with the CNC machine drawing.
![Main model](/documentation/models/serverbot_process.png)

### Subprocess

The subprocess model includes the glass serving and notification that it has finished the subprocess activity.
![Subprocess model](/documentation/models/serverbot_subprocess.png)

## Attributions

This project was created during the Practical Course “Sustainable Process Automation: Humans, Software and the Mediator Pattern” at the TUM chair of Information Systems and Business Process Management. It was multifaceted and highly engaging, providing valuable insights and thoughtful guidance throughout.

It leverages the solid foundation from the previously completed practical course project of **Lukas Rüger** which includes the conversion mechanisms from text and svgs to G-code and the CNC setup with essential control commands. The project can be found [here](https://github.com/lurueger/BierdeckelBot).

The project incorporates images sourced from the [SVGRepo](https://www.svgrepo.com/) that are used for the logo library in the interface.

## Contribution

This project optimizes the bar experience by seamlessly automating the order creation, management, processing, and the serving workflow. It minimizes and eliminates redundant manual tasks, such as specifying file names, adjusting font sizes, or manually initiating the printing and serving processes. The system integrates separate services, which are designed to be reusable, allowing for flexibility and easy future enhancements. These services exchange data through the Cloud Process Execution Engine (CPEE), which orchestrates the overall workflow, ensuring seamless interaction between the services, and managing all the components.
The orchestration allows for parallelized subprocesses, increasing efficiency by handling tasks concurrently where possible. By streamlining these processes, the project provides a more efficient system, where the bar operation is optimized.

## Outlook

While many intermediate steps have been eliminated, the system still relies on certain conditions that require manual supervision. For instance, the glass and coaster from a previous order must be removed from the component before the next items are served, to prevent **potential collisions**. To improve reliability, the system would benefit from the integration of an **error management and safety** framework. This would ensure that the process remains uninterrupted by wrongful interventions or the absence of certain components, preventing unpredictable behavior.
Additionally, the system could be optimized further by **scaling** it to multiple serving stations.
To achieve a fully immersive experience, the process would need to **also integrate the actual cocktail preparation**, such as dispensing the chosen recipe from the beverage station – a step that was excluded from the scope of this project. It would be most effective to incorporate this stage into the parallel branch responsible for serving the glass. Since the other parallel branch, which handles the coaster printing, is the most time-consuming, it offers an opportunity to run the cocktail preparation concurrently. This would significantly reduce the overall time required, optimizing efficiency and fully leveraging the potential for parallel processing.
