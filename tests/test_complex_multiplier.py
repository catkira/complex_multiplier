import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotb.triggers import RisingEdge, ReadOnly
from fixedpoint import FixedPoint

import random
import warnings
import logging

with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    from cocotb.generators.byte import random_data, get_bytes

from complex_multiplier_model import Model

CLK_PERIOD_NS = 100


class TB(object):
    def __init__(self,dut):
        self.dut = dut
        self.input_width_a = int(dut.INPUT_WIDTH_A.value)
        self.input_width_b = int(dut.INPUT_WIDTH_B.value)
        self.output_width = int(dut.OUTPUT_WIDTH.value)
        self.stages = int(dut.STAGES.value)
        
        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)        
        
        cocotb.fork(Clock(dut.clk, CLK_PERIOD_NS, units='ns').start())
        
    async def cycle_reset(self):
        self.dut.rst.setimmediatevalue(1)
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        self.dut.rst <= 0
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        self.dut.rst <= 1
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)



# Test single multiplication
@cocotb.test()
async def single_multiplication_(dut):
    """Perform a single multiplication of two complex numbers

    Expected Results:
        a*b = (a_r*b_r - a_i*b_i) + j(a_r*b_i + a_i*b_r)
    """
    tb = TB(dut)
    await tb.cycle_reset()
    
    a_bytes = get_bytes(int(tb.input_width_a/8),random_data())
    b_bytes = get_bytes(int(tb.input_width_b/8),random_data())

    dut.s_axis_a_tdata <= int.from_bytes(a_bytes, byteorder='big', signed=False)
    dut.s_axis_b_tdata <= int.from_bytes(b_bytes, byteorder='big', signed=False)
    await Timer(CLK_PERIOD_NS * tb.stages, units='ns')

    receivedData = dut.m_axis_tdata.value.buff
    received_r = receivedData[int(len(receivedData)/2):len(receivedData)]
    received_i = receivedData[0:int(len(receivedData)/2)]

    await Timer(CLK_PERIOD_NS * 2, units='ns')
    model = Model(tb.input_width_a,tb.input_width_b,tb.output_width) 
    calculatedData = model.calculate(a_bytes,b_bytes)
    calculated_i = calculatedData[0:int(tb.output_width/8/2)]
    calculated_r = calculatedData[int(tb.output_width/8/2):int(tb.output_width/8)]
    assert received_r == calculated_r, ("real part should have been %i but was %i " % 
                           (int.from_bytes(calculated_r,byteorder='big',signed=True),int.from_bytes(received_r,byteorder='big',signed=True)))
    assert received_i == calculated_i, ("imaginary part should have been %i but was %i " % 
                           (int.from_bytes(calculated_i,byteorder='big',signed=True),int.from_bytes(received_i,byteorder='big',signed=True)))
    assert calculatedData == receivedData, ("Error, expected %s got %s" % (calculatedData.hex(), receivedData.hex()))
    #dut._log.info("0x%08X * 0x%08X" % (A, B))

# Test multiple multiplications
@cocotb.test()
async def multiple_multiplications_(dut):
    tb = TB(dut)
    await tb.cycle_reset()
    
    for k in range(20):
        a_bytes = get_bytes(int(tb.input_width_a/8),random_data())
        b_bytes = get_bytes(int(tb.input_width_b/8),random_data())

        dut.s_axis_a_tdata <= int.from_bytes(a_bytes, byteorder='big', signed=False)
        dut.s_axis_b_tdata <= int.from_bytes(b_bytes, byteorder='big', signed=False)
        await Timer(CLK_PERIOD_NS * tb.stages, units='ns')

        receivedData = dut.m_axis_tdata.value.buff
        received_r = receivedData[int(len(receivedData)/2):len(receivedData)]
        received_i = receivedData[0:int(len(receivedData)/2)]

        model = Model(tb.input_width_a,tb.input_width_b,tb.output_width) 
        calculatedData = model.calculate(a_bytes,b_bytes)
        calculated_i = calculatedData[0:int(tb.output_width/8/2)]
        calculated_r = calculatedData[int(tb.output_width/8/2):int(tb.output_width/8)]
        assert received_r == calculated_r, ("real part should have been %i but was %i " % 
                            (int.from_bytes(calculated_r,byteorder='big',signed=True),int.from_bytes(received_r,byteorder='big',signed=True)))
        assert received_i == calculated_i, ("imaginary part should have been %i but was %i " % 
                            (int.from_bytes(calculated_i,byteorder='big',signed=True),int.from_bytes(received_i,byteorder='big',signed=True)))
        assert calculatedData == receivedData, ("Error, expected %s got %s" % (calculatedData.hex(), receivedData.hex()))
