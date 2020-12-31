import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotb.triggers import RisingEdge, ReadOnly
from fixedpoint import FixedPoint

import random
import warnings

CLK_PERIOD_NS = 100


def setup_dut(dut):
    cocotb.fork(Clock(dut.clk, CLK_PERIOD_NS, units='ns').start())

# Test single multiplication
@cocotb.test()
async def single_multiplication_0(dut):
    """Perform a single multiplication of two complex numbers

    Test ID: 0

    Expected Results:
        a*b = (a_r*b_r - a_i*b_i) + j(a_r*b_i + a_i*b_r)
    """

    # Reset
    dut.rst <= 1
    setup_dut(dut)
    await Timer(CLK_PERIOD_NS * 1, units='ns')
    dut.rst <= 0
    await Timer(CLK_PERIOD_NS * 2, units='ns')
    dut.rst <= 1
    await Timer(CLK_PERIOD_NS * 2, units='ns')
	
    input_width_a = 16
    input_width_b = 16
    output_width = 32

    a_r = FixedPoint(0x10, signed=True,m=input_width_a/2)
    a_i = FixedPoint(0x20, signed=True,m=input_width_a/2)
    b_r = FixedPoint(2, signed=True,m=input_width_a/2)
    b_i = FixedPoint(3, signed=True,m=input_width_a/2)
    numStages = 3

    a_i.resize(input_width_a,0)
    dut.s_axis_a_tdata <= int((a_i << int(input_width_a/2)) + a_r)
    b_i.resize(input_width_a,0)
    dut.s_axis_b_tdata <= int((b_i << int(input_width_b/2)) + b_r)
    await Timer(CLK_PERIOD_NS * numStages, units='ns')

    receivedValue = int(dut.m_axis_tdata).to_bytes(length=int(output_width/8),byteorder='big',signed=False)
    received_i = int.from_bytes(receivedValue[int(len(receivedValue)/2):len(receivedValue)], byteorder='big', signed=True)
    received_r = int.from_bytes(receivedValue[0:int(len(receivedValue)/2)],byteorder='big',signed=True)

    correctResult = (FixedPoint(a_r*b_r - a_i*b_i,True,output_width)<<int(output_width/2)) + FixedPoint(a_r*b_r - a_i*b_i,True,output_width)
    await Timer(CLK_PERIOD_NS * 2, units='ns')
    assert received_r == a_r*b_r - a_i*b_i, ("(%i + j%i) * (%i + j%i), real part should have been "
                           "%i but was %i " % (a_r,a_i,b_r,b_i,
                           a_r*b_r - a_i*b_i,received_r))
    assert received_i == a_r*b_i + a_i*b_r, ("(%i + j%i) * (%i + j%i), imaginary part should have been "
                           "%i but was %i " % (a_r,a_i,b_r,b_i,
                           a_r*b_i + a_i*b_r,received_i))
    #dut._log.info("0x%08X * 0x%08X" % (A, B))

	