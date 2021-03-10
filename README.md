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
- ROUND_MODE      : if set to 0 output is truncated, otherwise output is rounded using rounding_cy input

## Ports
- clk           : clock
- aresetn       : active low reset
- rounding_cy   : bit used to balance rounding (should be randomly distributed between 0 and 1)
- s_axis_a      : input a AXI Stream inteface
- s_axis_b      : input b AXI Stream inteface
- m_axis_dout   : output AXI Stream inteface

## Rounding
If ROUND_MODE is set to 0, truncation (aka round-down or round-to-negative-infinity) will be used. This method has about half a bif dc offset in negative direction. [This](https://en.wikipedia.org/wiki/Rounding) Wikipedia page says that truncation is like rounding-towards-zero, however this is not the case for 2s complement numbers.
If TRUNCATE is set to 0, random rounding will be used. The input *rounding_cy* is then used as tie-breaker and should be toggled randomly. If rounding_cy is permanently tied to 0, the core will do round-half-away-from-zero, which does not have overall bias but bias towards zero. This is still better than just truncation. This [document](https://www.xilinx.com/support/documentation/ip_documentation/cmpy/v6_0/pg104-cmpy.pdf) describes different signals that can be connected to *rounding_cy* to implement other unbiased rounding methods like round-towards-zero.
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