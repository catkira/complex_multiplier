import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotb.triggers import RisingEdge, ReadOnly
from fixedpoint import FixedPoint

import random
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    from cocotb.generators.byte import random_data, get_bytes


CLK_PERIOD_NS = 100


def setup_dut(dut):
    cocotb.fork(Clock(dut.clk, CLK_PERIOD_NS, units='ns').start())

# Test single multiplication
@cocotb.test()
async def single_multiplication_(dut):
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
	
    input_width_a = int(dut.INPUT_WIDTH_A.value)
    input_width_b = int(dut.INPUT_WIDTH_B.value)
    output_width = int(dut.OUTPUT_WIDTH.value)

    a_i = FixedPoint(int.from_bytes(get_bytes(int(input_width_a/2/8),random_data()), byteorder='big',signed=False), signed=False,m=input_width_a/2)
    a_r = FixedPoint(int.from_bytes(get_bytes(int(input_width_a/2/8),random_data()), byteorder='big',signed=False), signed=False,m=input_width_a/2)
    b_r = FixedPoint(int.from_bytes(get_bytes(int(input_width_b/2/8),random_data()), byteorder='big',signed=False), signed=False,m=input_width_b/2)
    b_i = FixedPoint(int.from_bytes(get_bytes(int(input_width_b/2/8),random_data()), byteorder='big',signed=False), signed=False,m=input_width_b/2)
    numStages = 3

    a_i.resize(input_width_a,0)
    dut.s_axis_a_tdata <= int((a_i << int(input_width_a/2)) + a_r)
    b_i.resize(input_width_a,0)
    dut.s_axis_b_tdata <= int((b_i << int(input_width_b/2)) + b_r)
    await Timer(CLK_PERIOD_NS * numStages, units='ns')

    receivedValue = int(dut.m_axis_tdata).to_bytes(length=int(output_width/8),byteorder='big',signed=False)
    received_i = receivedValue[int(len(receivedValue)/2):len(receivedValue)]
    received_r = receivedValue[0:int(len(receivedValue)/2)]

    await Timer(CLK_PERIOD_NS * 2, units='ns')
    calculated_r = int(int(a_r*b_r) - int(a_i*b_i)).to_bytes(byteorder='big',length=2,signed=True)
    # imag part can overfow even if output witdt is input_width_a + input_width_b
    # therefore implement a truncation mechanism here using FixedPoint(...)
    calculated_i = int(FixedPoint(a_r*b_i + a_i*b_r,signed=False,m=int(output_width/2),overflow_alert='ignore')).to_bytes(byteorder='big',length=2,signed=False)
    assert received_r == calculated_r, ("(%i + j%i) * (%i + j%i), real part should have been "
                           "%i but was %i " % (a_r,a_i,b_r,b_i,
                           int(a_r*b_r) - int(a_i*b_i),received_r))
    assert received_i == calculated_i, ("(%i + j%i) * (%i + j%i), imaginary part should have been "
                           "%i but was %i " % (a_r,a_i,b_r,b_i,
                           a_r*b_i + a_i*b_r,received_i))
    #dut._log.info("0x%08X * 0x%08X" % (A, B))

