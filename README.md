# Complex Multiplier with AXI Stream Interface

## Overview
The complex multiplier has two AXI stream inputs and one AXI stream output. It can be used in SDR (Software Defined Radio) applications, where up- or down-mixing is required.

## Implementation Details
If the output width equals INPUT_WIDTH_A + INPUT_WIDTH_B no truncation or rounding is necessary.
If the sum of the input widths is larger than the output width, truncation or rounding is necessary, which can be selected via the TRUNCATE parameter. If TRUNCATE = 1, the spare bits of the result are truncated by a right shift operation. If TRUNCATE = 0, the rounding_cy input is used to perform a rounding.
The code has been tested on a Xilinx Series 7 FPGA with Vivado 2020.2.

## Parameter
- INPUT_WIDTH_A : width of the input_a AXI Stream interface, must be multiple of 8
- INPUT_WIDTH_B : width of the input_b AXI Stream interface, must be multiple of 8
- OUTPUT_WIDTH  : width of the output AXI Stream interface, must be multiple of 8
- STAGES        : number of additional pipeline stages, should be at least 2
- BLOCKING      : support backpressuse if set to 1, not yet implemented
- TRUNCATE      : if set to 1 output is truncated, otherwise output is rounded using rounding_cy input

## Ports
- clk           : clock
- aresetn       : active low reset
- rounding_cy   : bit used to balance rounding (should be randomly distributed between 0 and 1)
- s_axis_a      : input a AXI Stream inteface
- s_axis_b      : input b AXI Stream inteface
- m_axis_dout   : output AXI Stream inteface

## Rounding
In this component random rounding is implemented. The input *rounding_cy* should be toggled randomly. If it is connected to 0, the core will do round-half-down, which has bias, but its still better than just truncation. This [document](https://www.xilinx.com/support/documentation/ip_documentation/cmpy/v6_0/pg104-cmpy.pdf) describes different signals that can be connected to *rounding_cy* to implement other unbiased rounding methods like round-towards-zero.
See [here](https://github.com/catkira/CIC#rounding) for more explainations on this topic. 

## Verification
To run the unit tests install
- python >3.8
- iverilog >1.4
- python modules: cocotb, cocotb_test, pytest, pytest-parallel, pytest-cov, cocotbext-axi >0.1.6, fixedpoint

and run pytest in the repo directory
```
pytest -v --workers 10
```
Alternatively cocotb tests can be run by using the Makefile in the tests folder. To run in go into the tests folder an type "make clean; make" 

## References
- https://www.xilinx.com/support/documentation/ip_documentation/cmpy/v6_0/pg104-cmpy.pdf

## License
GPL