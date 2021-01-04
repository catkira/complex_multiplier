import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotb.triggers import RisingEdge, ReadOnly
from fixedpoint import FixedPoint
from cocotbext.axi import AxiStreamFrame, AxiStreamSource, AxiStreamSink, AxiStreamMonitor
from collections import deque

import random
import warnings
import os
import logging
import cocotb_test.simulator
import pytest

with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    from cocotb.generators.byte import random_data, get_bytes

import importlib.util

CLK_PERIOD_NS = 100


class TB(object):
    def __init__(self,dut):
        random.seed(30) # reproducible tests
        self.dut = dut
        self.input_width_a = int(dut.INPUT_WIDTH_A.value)
        self.input_width_b = int(dut.INPUT_WIDTH_B.value)
        self.output_width = int(dut.OUTPUT_WIDTH.value)
        self.stages = int(dut.STAGES.value)
        self.truncate = int(dut.TRUNCATE.value)

        self.axis_input_width_a = ((self.input_width_a+15)//16)*16
        self.axis_input_width_b = ((self.input_width_b+15)//16)*16
        self.axis_output_width  = ((self.output_width+15)//16)*16

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)        
        
        tests_dir = os.path.abspath(os.path.dirname(__file__))
        model_dir = os.path.abspath(os.path.join(tests_dir, '../model/complex_multiplier_model.py'))
        spec = importlib.util.spec_from_file_location("complex_multiplier_model", model_dir)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        self.model = foo.Model(self.input_width_a,self.input_width_b,self.output_width,self.truncate) 
        
        cocotb.fork(Clock(dut.aclk, CLK_PERIOD_NS, units='ns').start())
        
        self.source_a = AxiStreamSource(dut, "s_axis_a", dut.aclk, byte_size=8)
        self.source_b = AxiStreamSource(dut, "s_axis_b", dut.aclk, byte_size=8)
        self.sink = AxiStreamSink(dut, "m_axis", dut.aclk)        
        #self.monitor = AxiStreamMonitor(dut, "m_axis", dut.aclk)

    def frameToIQ(self, rx_frame):
        receivedData = (rx_frame.tdata[0]).to_bytes(byteorder='big', length=self.axis_output_width//8)
        received_r = receivedData[len(receivedData)//2:len(receivedData)]
        received_i = receivedData[0:len(receivedData)//2]
        return [received_i, received_r]

    def frameToBytes(self, rx_frame):
        receivedData = (rx_frame.tdata[0]).to_bytes(byteorder='little', length=self.axis_output_width//8)
        return receivedData[::-1]

    def getRandomIQSample(self, width):
        real = random.randint(-2**(width//2-1)-1, 2**(width//2-1))
        imag = random.randint(-2**(width//2-1)-1, 2**(width//2-1))
        real_fp = FixedPoint(real, signed=True,m=width//2,n=0)
        imag_fp = FixedPoint(imag, signed=True,m=width//2,n=0)
        axis_width = ((width+15)//16)*16
        real_bytes = int(real_fp).to_bytes(length=axis_width//8//2, byteorder='big', signed=True)
        imag_bytes = int(imag_fp).to_bytes(length=axis_width//8//2, byteorder='big', signed=True)
        sample = real_bytes
        sample += imag_bytes
        return sample
        
    async def cycle_reset(self):
        self.dut.aresetn.setimmediatevalue(1)
        await RisingEdge(self.dut.aclk)
        await RisingEdge(self.dut.aclk)
        self.dut.aresetn <= 0
        await RisingEdge(self.dut.aclk)
        await RisingEdge(self.dut.aclk)
        self.dut.aresetn <= 1
        await RisingEdge(self.dut.aclk)
        await RisingEdge(self.dut.aclk)


# Test single multiplication
@cocotb.test()
async def single_multiplication_(dut):
    """Perform a single multiplication of two complex numbers

    Expected Results:
        a*b = (a_r*b_r - a_i*b_i) + j(a_r*b_i + a_i*b_r)
    """
    tb = TB(dut)
    await tb.cycle_reset()
    
    a_bytes = tb.getRandomIQSample(tb.input_width_a)
    b_bytes = tb.getRandomIQSample(tb.input_width_b)

    # send data, ignore tready
    tb.dut.rounding_cy <= 0
    await tb.source_a.send(AxiStreamFrame(a_bytes[::-1]))
    await tb.source_b.send(AxiStreamFrame(b_bytes[::-1]))
        
    rx_frame = await tb.sink.recv()
    byteOrder = 'big'
    [received_i, received_r] = tb.frameToIQ(rx_frame)

    calculatedData = tb.model.calculate(a_bytes,b_bytes,tb.dut.rounding_cy)
    calculated_i = calculatedData[0:tb.axis_output_width//8//2]
    calculated_r = calculatedData[tb.axis_output_width//8//2:tb.axis_output_width//8]
    assert received_r == calculated_r, ("real part should have been %i but was %i " % 
                           (int.from_bytes(calculated_r,byteorder=byteOrder,signed=True),
                           int.from_bytes(received_r,byteorder=byteOrder,signed=True)))
    assert received_i== calculated_i, ("imaginary part should have been %i but was %i " % 
                           (int.from_bytes(calculated_i,byteorder=byteOrder,signed=True),int.from_bytes(received_i,byteorder=byteOrder,signed=True)))
    assert calculatedData == tb.frameToBytes(rx_frame), ("Error, expected %s got %s" % (calculatedData.hex(), tb.frameToBytes(rx_frame).hex()))
    await RisingEdge(dut.aclk)

# Test multiple multiplications
@cocotb.test()
async def multiple_multiplications_(dut):
    tb = TB(dut)    
    await tb.cycle_reset()
    #tb.sink.queue = deque() # remove remaining items from last test    
    test_data_list = []
    for i in range(20):
        a_bytes = tb.getRandomIQSample(tb.input_width_a)
        b_bytes = tb.getRandomIQSample(tb.input_width_b)
        
        tb.dut.rounding_cy <= 0
        await tb.source_a.send(AxiStreamFrame(a_bytes[::-1]))
        await tb.source_b.send(AxiStreamFrame(b_bytes[::-1]))
        
        test_data = [a_bytes,b_bytes,tb.dut.rounding_cy]
        test_data_list.append(test_data)
        await RisingEdge(dut.aclk)
        
    dut.s_axis_a_tvalid <= 0
    dut.s_axis_b_tvalid <= 0
    await RisingEdge(dut.aclk)    
    byteOrder = 'big'
    for test_data in test_data_list:
        rx_frame = await tb.sink.recv()
        [received_i, received_r] = tb.frameToIQ(rx_frame)

        calculatedData = tb.model.calculate(test_data[0],test_data[1],test_data[2])
        calculated_i = calculatedData[0:tb.axis_output_width//8//2]
        calculated_r = calculatedData[tb.axis_output_width//8//2:tb.axis_output_width//8]
        assert received_r == calculated_r, ("real part should have been %i but was %i " % 
                            (int.from_bytes(calculated_r,byteorder=byteOrder,signed=True),int.from_bytes(received_r,byteorder=byteOrder,signed=True)))
        assert received_i == calculated_i, ("imaginary part should have been %i but was %i " % 
                            (int.from_bytes(calculated_i,byteorder=byteOrder,signed=True),int.from_bytes(received_i,byteorder=byteOrder,signed=True)))
        assert calculatedData == tb.frameToBytes(rx_frame), ("Error, expected %s got %s" % (calculatedData.hex(), tb.frameToBytes(rx_frame).hex()))
        await RisingEdge(dut.aclk)
        
# cocotb-test

tests_dir = os.path.abspath(os.path.dirname(__file__))
rtl_dir = os.path.abspath(os.path.join(tests_dir, '..', 'hdl'))

@pytest.mark.parametrize("input_width_a", [16, 20, 32])
@pytest.mark.parametrize("input_width_b", [16, 32])
@pytest.mark.parametrize("output_width", [32, 22, 16])  # TODO: implement support for 24 bit output
@pytest.mark.parametrize("blocking", [1])
@pytest.mark.parametrize("truncate", [1, 0])
@pytest.mark.parametrize("stages", [3, 2])
def test_complex_multiplier(request, blocking, input_width_a, input_width_b, output_width, truncate, stages):
    dut = "complex_multiplier"
    module = os.path.splitext(os.path.basename(__file__))[0]
    toplevel = dut

    verilog_sources = [
        os.path.join(rtl_dir, f"{dut}.v"),
    ]

    parameters = {}

    parameters['INPUT_WIDTH_A'] = input_width_a
    parameters['INPUT_WIDTH_B'] = input_width_b
    parameters['OUTPUT_WIDTH'] = output_width
    parameters['BLOCKING'] = blocking
    parameters['TRUNCATE'] = truncate
    parameters['STAGES'] = stages

    extra_env = {f'PARAM_{k}': str(v) for k, v in parameters.items()}
    sim_build="sim_build/" + "_".join(("{}={}".format(*i) for i in parameters.items()))
    cocotb_test.simulator.run(
        python_search=[tests_dir],
        verilog_sources=verilog_sources,
        toplevel=toplevel,
        module=module,
        parameters=parameters,
        sim_build=sim_build,
        extra_env=extra_env,
    )

        
