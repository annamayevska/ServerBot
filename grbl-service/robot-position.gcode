G21 ; millimeters
G90 ; absolute coordinate
G0 Z0 ; Ensure that pen is lifted off properly before moving the bed
G0 X0 Y90 Z0 ; Lines 3-5 ensure that the gcode is not marked as finished, before the actual movement is finished
G0 X0 Y100 Z0
G0 X0 Y110 Z0
G0 X0 Y120 Z0 
G0 X0 Y130 Z0
G0 X0 Y140 Z0
G1 X0 Y149 Z0 F1000
G1 X0 Y150 Z0 ; Final position for robot access

M2